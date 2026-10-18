# Apache License, Version 2.0

Copyright 2025–2026 Alberto Martínez Zurita

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

---

## Origin of the code

Parts of this repository (the chaos proxy and its configuration, the circuit breaker,
the deterministic agent, the playbook registry and storage, reporting, and several tests
and assets) are derived from the **Chaos Playbook Engine**
(<https://github.com/alberto-martinez-zurita/chaos-playbook-engine>), which is published
under the Creative Commons Attribution-ShareAlike 4.0 International license (CC BY-SA 4.0).

Its author, Alberto Martínez Zurita, licenses the parts derived from it in this repository
under the Apache License, Version 2.0, as stated above. The Chaos Playbook Engine itself
remains available under CC BY-SA 4.0.

## Why Apache-2.0 for this artifact

This repository is the public reproducibility bundle for the paper below: the chaos rig,
the playbooks, the 128,800-run dataset and the analysis scripts. Apache-2.0 was chosen for:

- **Permissive use**—researchers and practitioners can build on the artifact freely,
  including in proprietary systems.
- **Explicit patent grant**—the patent clause (§3) protects downstream users from
  patent claims by contributors.
- **Compatibility** with most other open-source licenses, including MIT, BSD and LGPL.

## Citation

If you use this artifact, please cite the paper:

> Alberto Martínez Zurita and Alessandro Russo. *Mapping LLM-agent reliability under chaos:
> a cross-architecture study of structured recovery playbooks.* Chaos Playbook Lab, Working
> Paper 1, v1.1, October 2026. arXiv identifier to be added on submission.

The full Apache 2.0 license text is available at:
https://www.apache.org/licenses/LICENSE-2.0.txt
