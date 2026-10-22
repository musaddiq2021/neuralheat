# Windows release verification provenance

On **2026-10-22**, the maintainer stated during public-release preparation:

> NeuralHeat Studio is now built, installed, and verified on Windows.

This records **maintainer-confirmed Windows verification**. It is not a newly generated automated test result and does not invent individual test outcomes or a clean-machine certification.

The existing prepared installer is `NeuralHeat-Studio-Setup.exe`, **1,863,668,204 bytes**, SHA256:

```text
861038b7f183f936db1a545d20d148c113fc31c00ae62ba1a00a043a0b8e64a9
```

Publication preparation rehashed that artifact and confirmed it unchanged. The older restricted-executor installation attempt was denied Start Menu/uninstall-registry access and rolled back; its local report remains intact and is excluded from the source repository. Original frozen portable-release CPU, CUDA, WebView2 and worker test reports also remain preserved locally.

Detailed normal-Windows test output can be archived with the release when available. The maintainer confirmation above is the current public provenance for successful installation; publication preparation did not reinstall or rebuild the software.
