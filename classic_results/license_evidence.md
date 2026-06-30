# External Tool License and Build Evidence

Date: 2026-06-29

This file records the local evidence used by `REPORT.md` for tools that were not all equally available as open-source binaries.

| Tool | Local / official evidence | Conclusion used in the report |
| --- | --- | --- |
| hMETIS | UMN Technology Commercialization page: `https://license.umn.edu/product/hmetis-version-15` | The official distribution is described as a non-open, fee-based version of METIS, so I did not use an unofficial binary for the demo. |
| PaToH | `.tooling/patoh_extracted/build/Linux-x86_64/README` | The standalone binary was used for demo/research validation. Commercial or product use needs separate license confirmation. |
| Mt-KaHyPar | `.tooling/src/mt-kahypar/LICENSE` | Source tree is MIT licensed. The local CLI was compiled and run against the hMETIS `.hgr` input. |
| ABKGroup/TritonPart standalone | `.tooling/src/TritonPart/LICENSE` | The repository is BSD-3-Clause licensed; the standalone build was blocked by dependency/source compatibility, not by a repo license blocker. |
| ABKGroup/TritonPart standalone build | `.tooling/src/TritonPart/openroad_build.log` | CMake passed, but the OpenROAD target failed while compiling FastRoute because fmt 9 cannot format `grt::RouteType` without a formatter specialization. |

