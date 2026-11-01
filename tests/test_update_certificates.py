import sys
import unittest
from unittest.mock import Mock, patch

from python import update


class UpdateCertificateTests(unittest.TestCase):
    def test_system_trust_is_opt_in_and_enabled_before_update_io(self):
        for enabled in [False, True]:
            with self.subTest(enabled=enabled):
                truststore = Mock()
                with (
                    patch.dict(sys.modules, {"truststore": truststore}),
                    patch.object(update.sys, "version_info", (3, 10)),
                    patch.object(update, "export_logos_manifest") as export_logos,
                ):
                    def stop_before_io(*args, **kwargs) -> None:
                        self.assertEqual(truststore.inject_into_ssl.call_count, int(enabled))
                        raise RuntimeError("Stopping before update IO")

                    export_logos.side_effect = stop_before_io
                    with self.assertRaisesRegex(RuntimeError, "Stopping before update IO"):
                        update.main(system_certificates=enabled)

    def test_system_trust_rejects_unsupported_python_before_update_io(self):
        with (
            patch.object(update.sys, "version_info", (3, 9)),
            patch.object(update, "export_logos_manifest") as export_logos,
        ):
            with self.assertRaisesRegex(RuntimeError, "requires Python 3.10 or newer"):
                update.main(system_certificates=True)
            export_logos.assert_not_called()


if __name__ == "__main__":
    unittest.main()
