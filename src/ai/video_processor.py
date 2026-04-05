#!/usr/bin/env python3
"""Video processing for Xiaohongshu source posts."""

import hashlib
import os
import subprocess
import sys
from typing import List, Tuple

import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from config.config import DATA_DIR, MEDIA_DIR, OPENAI_API_KEY, OPENAI_TRANSCRIBE_MODEL, get_ai_runtime_mode, has_valid_openai_api_key
from src.ai.image_generator import ImageGenerator
from src.ai.text_llm_client import initialize_text_llm


class VideoProcessor:
    """Download, transcribe, and summarize source videos into note-friendly assets."""

    def __init__(self):
        self.client = None
        self.note_client = None
        self.use_ai_mode = False
        self.mode = "local"
        self.mode_reason = ""
        requested_mode = get_ai_runtime_mode("video_transcription_mode")
        try:
            self.note_client, _note_mode, _note_reason = initialize_text_llm(requested_mode, "视频阅读笔记")
        except Exception:
            self.note_client = None
        if requested_mode == "local":
            self.mode_reason = "设置为本地视频模式，不会调用 OpenAI 转写。"
            print("[INFO] {}".format(self.mode_reason))
        elif requested_mode == "ollama":
            self.mode = "ollama"
            self.mode_reason = "已启用 Ollama 视频模式：关键帧理解和视频笔记会走 Ollama，音频转写仍优先依赖 OpenAI Whisper。"
            print("[INFO] {}".format(self.mode_reason))
        elif requested_mode == "deepseek":
            self.mode_reason = "已选择 DeepSeek 视频转写，但当前视频转写仅支持 OpenAI Whisper，已退回本地模式。"
            print("[INFO] {}".format(self.mode_reason))
        elif has_valid_openai_api_key(OPENAI_API_KEY):
            try:
                from openai import OpenAI

                self.client = OpenAI(api_key=OPENAI_API_KEY)
                self.use_ai_mode = True
                self.mode = "openai"
                self.mode_reason = "已启用 OpenAI 视频转写模式"
                print("[OK] {}".format(self.mode_reason))
            except Exception as exc:
                self.mode_reason = "OpenAI 视频转写初始化失败，已退回本地模式：{}".format(str(exc)[:80])
                print("[WARNING] {}".format(self.mode_reason))
        else:
            self.mode_reason = (
                "已选择 OpenAI 视频转写，但未配置有效 API Key，已退回本地模式"
                if requested_mode == "openai"
                else "未配置有效 OPENAI_API_KEY，视频转写使用本地模式"
            )
            print("[INFO] {}".format(self.mode_reason))

        self.video_dir = os.path.join(MEDIA_DIR, "videos")
        self.audio_dir = os.path.join(MEDIA_DIR, "audio")
        self.frame_dir = os.path.join(MEDIA_DIR, "frames")
        for path in (self.video_dir, self.audio_dir, self.frame_dir):
            os.makedirs(path, exist_ok=True)

        self.image_generator = ImageGenerator()
        self.request_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.xiaohongshu.com/",
        }

    def process_post(self, post):
        processed = dict(post or {})
        processed["media_type"] = "video"

        video_url = self._select_downloadable_video_url(processed)
        if not video_url:
            processed["video_error"] = "missing_original_video_url"
            return processed

        if video_url.startswith("//"):
            video_url = "https:" + video_url
        processed["original_video_url"] = video_url

        video_path = self._download_video(video_url)
        if not video_path:
            processed["video_error"] = "download_failed"
            return processed

        processed["original_video_path"] = video_path

        audio_path = self._extract_audio(video_path)
        if not audio_path:
            processed["video_error"] = "audio_extract_failed"
            return processed
        processed["video_audio_path"] = audio_path

        transcript = self._transcribe_audio(audio_path)
        if not transcript and self.mode == "ollama":
            transcript = self._build_fallback_transcript(processed)
            processed["video_transcript_inferred"] = bool(transcript)
        if not transcript:
            processed["video_error"] = "transcript_failed"
            return processed
        processed["video_transcript"] = transcript

        frame_paths = self._extract_keyframes(video_path)
        if not frame_paths:
            processed["video_error"] = "frame_extract_failed"
            return processed
        processed["video_frame_paths"] = frame_paths

        frame_insights, frame_summary = self.image_generator.analyze_image_paths(frame_paths)
        if len(frame_insights) < 2:
            processed["video_error"] = "frame_insights_missing"
            return processed

        processed["video_frame_insights"] = frame_insights
        processed["video_summary"] = self._build_video_summary(processed, transcript, frame_summary)

        # Keep existing downstream image-only publish path working by exposing keyframes as final images.
        processed["image_summary"] = frame_summary
        processed["image_insights"] = frame_insights
        processed["final_image_paths"] = frame_paths
        processed["final_image_count"] = len(frame_paths)
        processed["generated_image_path"] = frame_paths[0]
        processed["image_mode"] = "video_frames"
        return processed

    def _download_video(self, url: str) -> str:
        if not self._is_downloadable_video_url(url):
            print("[WARNING] Skip non-downloadable video url: {}".format(str(url)[:120]))
            return ""
        file_hash = hashlib.md5(url.encode("utf-8")).hexdigest()[:12]
        path = os.path.join(self.video_dir, "xhs_video_{}.mp4".format(file_hash))
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path

        try:
            with requests.get(url, headers=self.request_headers, timeout=60, stream=True) as response:
                response.raise_for_status()
                with open(path, "wb") as fh:
                    for chunk in response.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            fh.write(chunk)
            return path if os.path.exists(path) and os.path.getsize(path) > 0 else ""
        except Exception as exc:
            print("[WARNING] Video download failed: {}".format(str(exc)[:100]))
            return ""

    def _extract_audio(self, video_path: str) -> str:
        ffmpeg_exe = self._get_ffmpeg_exe()
        if not ffmpeg_exe:
            return ""

        file_hash = hashlib.md5(video_path.encode("utf-8")).hexdigest()[:12]
        audio_path = os.path.join(self.audio_dir, "xhs_audio_{}.mp3".format(file_hash))
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            return audio_path

        command = [
            ffmpeg_exe,
            "-y",
            "-i",
            video_path,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            "64k",
            audio_path,
        ]
        try:
            subprocess.run(command, capture_output=True, check=True)
            return audio_path if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0 else ""
        except Exception as exc:
            print("[WARNING] Audio extraction failed: {}".format(str(exc)[:100]))
            return ""

    def _extract_keyframes(self, video_path: str, interval_seconds: int = 8, max_frames: int = 6) -> List[str]:
        ffmpeg_exe = self._get_ffmpeg_exe()
        if not ffmpeg_exe:
            return []

        duration = self._probe_duration(video_path)
        if duration <= 0:
            capture_times = [1, 3, 6]
        else:
            capture_times = []
            current = 1
            while current < duration and len(capture_times) < max_frames:
                capture_times.append(int(current))
                current += interval_seconds
            if not capture_times:
                capture_times = [max(1, int(duration / 2))]

        file_hash = hashlib.md5(video_path.encode("utf-8")).hexdigest()[:12]
        frame_paths = []
        for index, second in enumerate(capture_times[:max_frames]):
            frame_path = os.path.join(self.frame_dir, "xhs_frame_{}_{}.jpg".format(file_hash, index))
            if not os.path.exists(frame_path) or os.path.getsize(frame_path) == 0:
                command = [
                    ffmpeg_exe,
                    "-y",
                    "-ss",
                    str(second),
                    "-i",
                    video_path,
                    "-frames:v",
                    "1",
                    "-q:v",
                    "2",
                    frame_path,
                ]
                try:
                    subprocess.run(command, capture_output=True, check=True)
                except Exception as exc:
                    print("[WARNING] Keyframe extraction failed at {}s: {}".format(second, str(exc)[:100]))
                    continue
            if os.path.exists(frame_path) and os.path.getsize(frame_path) > 0:
                frame_paths.append(frame_path)
        return frame_paths

    def _probe_duration(self, video_path: str) -> float:
        try:
            import imageio_ffmpeg

            _frame_count, duration = imageio_ffmpeg.count_frames_and_secs(video_path)
            return float(duration or 0)
        except Exception:
            return 0.0

    def _transcribe_audio(self, audio_path: str) -> str:
        if not self.client:
            print("[WARNING] OpenAI API unavailable, cannot transcribe video audio")
            return ""

        try:
            with open(audio_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    model=OPENAI_TRANSCRIBE_MODEL,
                    file=audio_file,
                    response_format="text",
                )
            if isinstance(response, str):
                return response.strip()
            text = getattr(response, "text", "") or ""
            return str(text).strip()
        except Exception as exc:
            print("[WARNING] Audio transcription failed: {}".format(str(exc)[:100]))
            return ""

    def _build_video_summary(self, post, transcript: str, frame_summary: str) -> str:
        title = (post.get("original_title") or post.get("title") or "").strip()
        body = (post.get("original_content") or post.get("content") or "").strip()
        transcript_summary = self._summarize_transcript(transcript)

        if self.note_client:
            try:
                response = self.note_client.chat.completions.create(
                    model=getattr(self.note_client, "default_model", None),
                    messages=[
                        {
                            "role": "system",
                            "content": "请用中文总结视频内容，输出 3-4 句高信息密度摘要，优先保留事实、步骤、结论。",
                        },
                        {
                            "role": "user",
                            "content": "标题：{}\n原贴说明：{}\n转写内容：{}\n关键帧摘要：{}".format(
                                title,
                                body[:600],
                                transcript[:2000],
                                frame_summary[:1200],
                            ),
                        },
                    ],
                    temperature=0.2,
                    max_tokens=280,
                )
                content = (response.choices[0].message.content or "").strip()
                if content:
                    return content
            except Exception as exc:
                print("[WARNING] Video summary LLM failed: {}".format(str(exc)[:100]))

        parts = []
        if title:
            parts.append("视频主题：{}".format(title))
        if body:
            parts.append("原贴说明：{}".format(body[:180]))
        if transcript_summary:
            parts.append("转写摘要：{}".format(transcript_summary))
        if frame_summary:
            parts.append("画面摘要：{}".format(frame_summary))
        return "\n".join(parts)

    def _build_fallback_transcript(self, post) -> str:
        parts = []
        title = (post.get("original_title") or post.get("title") or "").strip()
        body = (post.get("original_content") or post.get("content") or "").strip()
        if title:
            parts.append("标题：{}".format(title))
        if body:
            parts.append("原贴说明：{}".format(body[:1200]))
        return "\n".join(parts).strip()

    def _summarize_transcript(self, transcript: str, max_points: int = 4) -> str:
        lines = []
        seen = set()
        for part in transcript.replace("\r", "\n").split("\n"):
            sentence = part.strip()
            if len(sentence) < 8:
                continue
            if sentence in seen:
                continue
            seen.add(sentence)
            lines.append(sentence)
            if len(lines) >= max_points:
                break
        if lines:
            return "；".join(lines)
        return transcript[:220].strip()

    def _get_ffmpeg_exe(self) -> str:
        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:
            print("[WARNING] imageio-ffmpeg unavailable: {}".format(str(exc)[:100]))
            return ""

    def _select_downloadable_video_url(self, post) -> str:
        candidates = []
        primary = str(post.get("original_video_url") or "").strip()
        if primary:
            candidates.append(primary)
        for url in post.get("video_urls", []) or []:
            url = str(url or "").strip()
            if url:
                candidates.append(url)

        seen = set()
        for url in candidates:
            if url.startswith("//"):
                url = "https:" + url
            if url in seen:
                continue
            seen.add(url)
            if self._is_downloadable_video_url(url):
                return url
        return ""

    def _is_downloadable_video_url(self, url: str) -> bool:
        url = str(url or "").strip().lower()
        if not url:
            return False
        if url.startswith(("blob:", "data:", "mediastream:", "filesystem:")):
            return False
        return url.startswith("http://") or url.startswith("https://")
