# NVIDIA licensing enquiry — draft, not sent

**Historical fallback only.** The verified v1.0.0-beta.1 installer omits Mg and passes real Windows installation/desktop checks. This enquiry is not required for that release; retain it only for a different payload that includes the component.

Use this only if publishing a payload that retains cuSOLVERMg, or if the exclusion candidate cannot complete all required verification. The removal route may avoid needing a grant for this particular file; it does not waive the licenses of the CUDA components still shipped. No email has been sent.

To: `nvidia-compute-license-questions@nvidia.com`

Subject: Written redistribution clarification for cusolverMg64_11.dll in a Windows PyTorch scientific application

Hello NVIDIA Licensing,

I am preparing NeuralHeat Studio, an independently developed Windows x64 scientific application for 2D heat diffusion and neural-surrogate inspection. Its own source is MIT licensed. NVIDIA proprietary runtimes remain separate works under their applicable agreements; we do not represent them as MIT licensed.

Please clarify the redistribution grant applicable to this exact binary:

| Attribute | Observed value |
|---|---|
| Actual filename | `cusolverMg64_11.dll` |
| Size | 157,071,360 bytes |
| SHA256 | `c3377f10606ff0606be2f08401d54aff6c37f137b78d6b6e21be356a5b4d6cc2` |
| Source | `torch/lib/cusolverMg64_11.dll` in the installed PyTorch `2.11.0+cu128` Windows distribution |
| Wheel RECORD | SHA256 `wzd_EGBv8GBr4vCEAdVK_2w38Te3jWtuIb41altNbMI`; byte match confirmed |
| CUDA runtime build | 12.8 |
| Associated cuSOLVER | `cusolverGetProperty` reports 11.7.3; the official CUDA 12.8.1 redistribution manifest identifies cuSOLVER 11.7.3.90 |
| Application location | `_internal/torch/lib/cusolverMg64_11.dll` in a PyInstaller onedir bundle |

The CUDA 12.8.1 EULA Attachment A lists `cusolver.dll` and permits certain architecture/version filename variants. It does not explicitly name cuSOLVERMg. The component license referenced by the official manifest also lists `cusolver.dll`, without explicitly naming the Mg DLL. We do not want to infer a grant for a different component merely from the cuSOLVER family name.

References:

- [CUDA 12.8.1 agreement and Attachment A](https://docs.nvidia.com/cuda/archive/12.8.1/eula/index.html#attachment-a)
- [CUDA 12.8.1 redistribution manifest](https://developer.download.nvidia.com/compute/cuda/redist/redistrib_12.8.1.json)
- [cuSOLVER component license](https://developer.download.nvidia.com/compute/cuda/redist/libcusolver/LICENSE.txt)
- [cuSOLVER 12.8 documentation distinguishing the Mg API](https://docs.nvidia.com/cuda/archive/12.8.1/cusolver/index.html)

Could you confirm in writing:

1. Whether the exact cuSOLVERMg DLL above may be distributed unmodified as part of this application under the cited CUDA grant, and precisely which agreement/redistributable listing establishes that permission.
2. If not, which additional license or express permission is required, and how an individual open-source developer can obtain it.
3. Which notices, end-user restrictions and other accompanying materials must be delivered for this exact component.

The application adds heat simulation, a trained CNN, model inspection, training controls and performance reports. It targets NVIDIA GPUs for CUDA operations and provides an independent CPU fallback. The NVIDIA runtimes would only be supplied as application dependencies, not as a standalone SDK, and would retain their notices. We would not require disclosure or modification of NVIDIA proprietary source.

PyInstaller collected the DLL from the PyTorch wheel, and PyTorch's Windows import code eagerly loads all DLLs present in its library directory. NeuralHeat does not call the multi-GPU eigensolver API. We are testing a separately packaged version omitting the DLL; no required DLL will be removed from the verified original application as an assumption.

Please identify any additional technical information needed to resolve the redistribution question. We will hold publication of a payload retaining this component until its applicable rights are established.

Thank you,

NeuralHeat Studio maintainer
