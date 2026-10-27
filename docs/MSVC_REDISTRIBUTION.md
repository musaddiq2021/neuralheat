# Microsoft runtime licence and provenance record

Reviewed: **27 October 2026**. **The MSVC licence/provenance review is resolved for the four unchanged release DLLs.** Publisher acceptance, the installed Community edition, exact official binary provenance and applicable distribution conditions are recorded. The separate Mg-free desktop/installation checks still determine Windows release readiness. No DLL, model or scientific result was replaced.

## Installed product and acceptance evidence

| Evidence | Observed value |
|---|---|
| Product | Visual Studio Community 2026, `Microsoft.VisualStudio.Product.Community` |
| Display/build version | `18.11.1` / `18.11.12315.225` |
| Installation | `C:\Program Files\Microsoft Visual Studio\18\Community` |
| Instance / channel | `b7bb7172` / `VisualStudio.18.Release` |
| Installation timestamp | `2026-10-22T12:24:14Z` |
| State | Complete, launchable, not prerelease; no reboot required |
| C++ desktop workload | `Microsoft.VisualStudio.Workload.NativeDesktop`, explicitly selected |
| Runtime component | `Microsoft.VisualStudio.Component.VC.Redist.14.Latest`, installed |
| Publisher statement, received 23 October | “Visual Studio Community 2026 is now installed, including the Desktop development with C++ workload. I accepted the Microsoft licence terms during installation.” |

Acceptance is recorded from the publisher's statement, **not inferred from installed DLLs or accepted by an automated tool**. The installation timestamp is not an independent timestamp of acceptance. The previously stated independent, personal MIT project falls within Microsoft's [individual developer usage category](https://visualstudio.microsoft.com/vs/community/#usage); employer/organization use would need its own assessment.

The setup catalog identifies https://go.microsoft.com/fwlink/?LinkId=2327616 as its licence link. The [official terms page](https://visualstudio.microsoft.com/license-terms/vs2026-ga-community/) supplies the [archived original DOCX](licenses/vendor/Microsoft-Visual-Studio-Community-2026.docx) and [readable extraction](licenses/vendor/Microsoft-Visual-Studio-Community-2026.txt). DOCX SHA256: `02ac07637f4a513a807cd3721c7620433fc483bc049d25784b0c10c54b05e1fb`; size 69,066 bytes; EULA ID `VS2026_Comm_ENU.1033`; updated 1 October 2025. Its full text and applicable Distributable Code conditions were reviewed on 27 October. Acceptance was already confirmed; no new acceptance is requested.

The [public provenance summary](licenses/msvc-provenance.json) records installation, publisher confirmation and exact file matches. Raw collector output is retained privately under `.cache/msvc-evidence/`. No account credentials or product keys are needed or collected.

## Official runtime files and exact comparisons

Licensed release CRT directory:

```text
C:\Program Files\Microsoft Visual Studio\18\Community\VC\Redist\MSVC\14.51.36231\x64\Microsoft.VC145.CRT
```

The directory is named **14.51.36231**, but its inspected DLL file versions are **14.51.36247.0**. No version match was guessed from the directory name.

Verified portable root: `D:\neuralheat\dist\desktop\20261021-184035-046\NeuralHeat Studio`.

| Bundled path beneath that root | DLL version | Bytes | Comparison with licensed release CRT |
|---|---|---:|---|
| `_internal\msvcp140.dll` | 14.51.36247.0 | 643,512 | SHA256 identical to vendor `msvcp140.dll` |
| `_internal\vcruntime140.dll` | 14.51.36247.0 | 178,616 | SHA256 identical to vendor `vcruntime140.dll` |
| `_internal\vcruntime140_1.dll` | 14.51.36247.0 | 50,112 | SHA256 identical to vendor `vcruntime140_1.dll` |
| `_internal\numpy.libs\msvcp140-a4c2229bdc2a2a630acdc095b4d86008.dll` | 14.40.33810.0 | 575,056 | **Exact match** to the official signed 14.40 package; separate from the installed 14.51 tree |

All four bundled files have valid Microsoft Authenticode signatures. Full hashes are in [msvc-binaries.json](licenses/msvc-binaries.json) and [msvc-provenance.json](licenses/msvc-provenance.json). Original PyInstaller TOCs establish that the three root files were collected from System32. That historical collection path is preserved; the new comparisons establish identical copies in the licensed vendor tree without rewriting the build record.

The official x64 runtime installer is also available locally:

```text
C:\Program Files\Microsoft Visual Studio\18\Community\VC\Redist\MSVC\v145\vc_redist.x64.exe
Version: 14.51.36247.0
Bytes: 18,731,856
SHA256: 843068991daaa1f73ad9f6239bce4d0f6a07a51f18c37ea2a867e9beca71295c
Authenticode: Valid; Microsoft Corporation
```

It was inspected, not run, added to the application or installed again.

## Applicable redistribution permission

The [Visual Studio 2026 REDIST list](https://learn.microsoft.com/en-us/visualstudio/releases/2026/redistribution#visual-c-runtime-files) permits a validly licensed Community user's unmodified release files from `VC\redist` and its subfolders, subject to the edition's licence terms. It excludes debug directories and prerelease/preview components. The installed `Licenses\1033\Redist.txt` points to that official list.

The three root DLLs have exact SHA256 matches in the permitted directory. Their file identity/source question is resolved; replacing identical bytes or rebuilding the scientific application serves no purpose. The edition's full distribution requirements must still be retained and observed. Microsoft's [deployment guidance](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files) documents application-local distribution and the official redistributable installer.

### NumPy's older runtime: official source and resolution

Microsoft's [winget-pkgs manifest for 14.40.33810.0 x64](https://github.com/microsoft/winget-pkgs/blob/master/manifests/m/Microsoft/VCRedist/2015%2B/x64/14.40.33810.0/Microsoft.VCRedist.2015%2B.x64.installer.yaml) identifies the exact official installer. The downloaded 25,397,512-byte file has a valid Microsoft Corporation signature and matches the manifest SHA256:

```text
3642e3f95d50cc193e4b5a0b0ffbf7fe2c08801517758b4c8aeb7105a091208a
```

CAB extraction, without installing the runtime, supplies `msvcp140.dll_amd64`, 575,056 bytes. Its SHA256 exactly equals NumPy's installed wheel, wheel RECORD and original frozen copy:

```text
a4c2229bdc2a2a630acdc095b4d86008e5c3e3bc7773174354f3da4f5beb9cde
```

The upstream hash-named DLL therefore contains unchanged official object code. Keep its required NumPy name and location. No replacement, import-table patch or runtime downgrade is needed.

The documented route combines the publisher's accepted Community **Distributable Code** grant with the [2026 REDIST list's separately downloaded runtime provision](https://learn.microsoft.com/en-us/visualstudio/releases/2026/redistribution#visual-c-runtime-files), which limits runtime package/individual-binary distribution to licensed Visual Studio users. The exact official package source is now established; this is not a claim that the older DLL exists in the current 14.51 tree. Microsoft's [v14 guidance](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) documents the common runtime family and licensed-user requirement.

The package's [runtime installation/use EULA](licenses/vendor/Microsoft-Visual-Cpp-Runtime-14.40-ENU.txt), ID `Cpp_2015-2022_ENU.1033`, is retained with its [original English RTF](licenses/vendor/Microsoft-Visual-Cpp-Runtime-14.40-ENU.rtf), SHA256 `8099dc3cf9502c335da829e5c755948a12e3e6de490eb492a99deb673d883d8b`. That EULA alone **does not grant redistribution**; the licensed Visual Studio distribution grant is the basis.

### Distribution conditions retained for this release

- NeuralHeat adds substantial primary functionality: simulation, inference, model/activation inspection, training and benchmarking.
- This record covers only the four inspected unmodified release object-code files. No Microsoft debug, preview or compiler/IDE component is distributed. The application's beta label does not make its stable Microsoft runtime a preview component.
- Setup presents MIT plus [protective binary conditions](licenses/BINARY_DISTRIBUTION_TERMS.txt); full upstream terms/notices accompany the application and release. Microsoft code is not relicensed under MIT or made subject to source-disclosure/modification obligations.
- Distributors and end users must preserve code/notices and observe the governing protections and applicable trade laws. Running NeuralHeat does not require Visual Studio.
- The publisher's already accepted distribution indemnity obligation remains applicable; it is not erased or transferred to ordinary users.

This is a documented licence/provenance assessment for the specified publisher and payload, not a new vendor permission letter. No second Visual Studio installation or vendor enquiry is required for this route. Reassess changed binaries or applicable terms rather than treating this record as a blanket grant.

### Reproduce the official comparison

```powershell
.\scripts\fetch_release_licences.ps1
.\.venv\Scripts\python.exe scripts/archive_community_licence.py --source .cache/licensing/Visual_Studio_2026-License-Community_ENU.docx
.\.venv\Scripts\python.exe scripts/inspect_msvc_runtime.py --installer .cache/licensing/VC_redist.x64-14.40.33810.exe --output .cache/licensing/runtime-14.40-evidence-new
```

Use a fresh extraction output directory. The fetcher checks the official installer hash/signature; the inspector refuses unpinned input before extraction. Original documents, CAB provenance and exact comparisons are retained separately from the legal assessment. Raw DLL extraction stays under ignored `.cache/licensing/`; no proprietary DLL is added to Git.

## Reproduction and future packaging

Read-only evidence collection:

```powershell
.\scripts\collect_msvc_evidence.ps1 `
  -VisualStudioRoot 'C:\Program Files\Microsoft Visual Studio\18\Community'

# Attach the already recorded publisher statement and archived terms:
.\scripts\collect_msvc_evidence.ps1 `
  -VisualStudioRoot 'C:\Program Files\Microsoft Visual Studio\18\Community' `
  -AcceptanceRecord '.cache\licensing\msvc-acceptance.json'
```

The collector creates a fresh private directory. It compares files; it never accepts terms, changes the application or automatically authorizes publication. The acceptance-record format supports a confirmation date when the exact acceptance time was not separately recorded.

For the next independently tested package, pin the licensed CRT directory and hashes instead of ambient System32 copies. Microsoft recommends its signed redistributable installer for servicing; it can be carried offline as a prerequisite with installed/newer-version handling. That does not remove NumPy's dependency on its hash-named application-local DLL. Do not replace, rename or delete that file without a separately licensed and tested upstream packaging change.

NeuralHeat remains MIT licensed; Microsoft components retain their own terms. This record does not clear the separate NVIDIA cuSOLVERMg/desktop-validation follow-up or authorize publishing the existing installer.
