import unittest

import server


class ServerCommandTests(unittest.TestCase):
    def setUp(self):
        self.original_extra_args = list(server.YTDLP_EXTRA_ARGS)

    def tearDown(self):
        server.YTDLP_EXTRA_ARGS = self.original_extra_args

    def test_download_command_includes_configured_ytdlp_extra_args(self):
        server.YTDLP_EXTRA_ARGS = [
            "--js-runtimes",
            "deno",
            "--remote-components",
            "ejs:npm",
        ]

        cmd = server.build_yt_dlp_command(
            "https://www.youtube.com/watch?v=abc123",
            "mp4",
            "720",
            r"C:\Downloads",
        )

        self.assertIn("--ignore-config", cmd)
        self.assertIn("--js-runtimes", cmd)
        self.assertIn("deno", cmd)
        self.assertIn("--remote-components", cmd)
        self.assertIn("ejs:npm", cmd)
        self.assertIn("--no-playlist", cmd)
        self.assertNotIn("--embed-metadata", cmd)
        self.assertNotIn("--postprocessor-args", cmd)

    def test_download_command_omits_extra_args_when_unconfigured(self):
        server.YTDLP_EXTRA_ARGS = []

        cmd = server.build_yt_dlp_command(
            "https://example.com/video.mp4",
            "mp4",
            "720",
            r"C:\Downloads",
        )

        self.assertIn("--ignore-config", cmd)
        self.assertNotIn("--js-runtimes", cmd)
        self.assertNotIn("--remote-components", cmd)
        self.assertNotIn("--embed-metadata", cmd)
        self.assertNotIn("--postprocessor-args", cmd)

    def test_build_ytdlp_extra_args_from_server_args(self):
        class Args:
            cookies_from_browser = "chrome"
            no_cookies_from_browser = False
            cookies = ""
            js_runtimes = "deno"
            remote_components = "ejs:npm"

        args = server.build_ytdlp_extra_args(Args())

        self.assertEqual(
            args,
            [
                "--cookies-from-browser",
                "chrome",
                "--js-runtimes",
                "deno",
                "--remote-components",
                "ejs:npm",
            ],
        )

    def test_audio_command_requires_audio_postprocessing_without_custom_metadata(self):
        server.YTDLP_EXTRA_ARGS = []

        cmd = server.build_yt_dlp_command(
            "https://example.com/video.mp4",
            "mp3",
            "720",
            r"C:\Downloads",
        )

        self.assertIn("-x", cmd)
        self.assertIn("--audio-format", cmd)
        self.assertIn("mp3", cmd)
        self.assertNotIn("--embed-metadata", cmd)
        self.assertNotIn("--postprocessor-args", cmd)


if __name__ == "__main__":
    unittest.main()
