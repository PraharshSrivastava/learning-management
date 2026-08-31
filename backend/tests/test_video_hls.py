from __future__ import annotations

from pathlib import Path

from app.generation import video


def test_generate_hls_playlist_packages_fmp4_segments(
    monkeypatch, tmp_path: Path
) -> None:
    mp4_path = tmp_path / "module_1.mp4"
    mp4_path.write_bytes(b"fake mp4")
    existing_hls = tmp_path / "module_1_hls"
    existing_hls.mkdir()
    (existing_hls / "old_segment.m4s").write_text("old", encoding="utf-8")

    captured_command: list[str] = []

    class Result:
        returncode = 0
        stderr = ""

    def fake_run(command, **kwargs):
        nonlocal captured_command
        captured_command = [str(part) for part in command]
        output_dir = Path(kwargs["cwd"])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "master.m3u8").write_text("#EXTM3U\n", encoding="utf-8")
        (output_dir / "init.mp4").write_bytes(b"init")
        (output_dir / "segment_0000.m4s").write_bytes(b"segment")
        return Result()

    monkeypatch.setattr(video.imageio_ffmpeg, "get_ffmpeg_exe", lambda: "ffmpeg")
    monkeypatch.setattr(video.subprocess, "run", fake_run)

    playlist = video.generate_hls_playlist(mp4_path)

    assert playlist == existing_hls / "master.m3u8"
    assert playlist.is_file()
    assert (existing_hls / "init.mp4").is_file()
    assert (existing_hls / "segment_0000.m4s").is_file()
    assert not (existing_hls / "old_segment.m4s").exists()
    assert "-hls_segment_type" in captured_command
    assert "fmp4" in captured_command
    assert "-hls_time" in captured_command
    assert "6" in captured_command
