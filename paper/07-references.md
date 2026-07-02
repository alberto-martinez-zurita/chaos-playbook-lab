# References

> All 44 entries were verified against primary sources on 2026-05-18 (arXiv
> abstract pages for [38]–[41], canonical protocol URLs for [32][33], vendor
> releases for the model reports [26]–[31]).

## Chaos engineering and fault injection

[1] Basiri, A., Behnam, N., De Rooij, R., Hochstein, L., Kosewski, L., Reynolds, J., & Rosenthal, C. (2016). **Chaos engineering**. *IEEE Software*, 33(3), 35–41.

[2] Bennett, C., & Tseitlin, A. (2012). **Chaos Monkey released into the wild**. Netflix Tech Blog. <https://netflixtechblog.com/chaos-monkey-released-into-the-wild-76f4ca6c2f55>

[3] Rosenthal, C., Hochstein, L., Blohowiak, A., Jones, N., & Basiri, A. (2017). **Principles of Chaos Engineering**. <https://principlesofchaos.org>

[4] Alvaro, P., Rosen, J., & Hellerstein, J. M. (2015). **Lineage-driven fault injection**. *ACM SIGMOD 2015*, 331–346.

[5] Alvaro, P., Andrus, K., Sanden, C., Rosenthal, C., Basiri, A., & Hochstein, L. (2016). **Automating failure testing research at internet scale**. *ACM Symposium on Cloud Computing (SoCC)*, 17–28.

[6] Gremlin Inc. (2024). **Gremlin Chaos Engineering Platform**. <https://www.gremlin.com>

[7] LitmusChaos contributors. (2024). **Litmus: Cloud-Native Chaos Engineering** (CNCF Incubating). <https://litmuschaos.io>

[8] Chaos Mesh contributors. (2024). **Chaos Mesh: A Cloud-Native Chaos Engineering Platform** (CNCF Incubating). <https://chaos-mesh.org>

## LLM agent benchmarks and frameworks

[9] Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., & Cao, Y. (2023). **ReAct: Synergizing reasoning and acting in language models**. *ICLR 2023*.

[10] Shinn, N., Cassano, F., Berman, E., Gopinath, A., Narasimhan, K., & Yao, S. (2023). **Reflexion: Language agents with verbal reinforcement learning**. *NeurIPS 2023*.

[11] Yao, S., Yu, D., Zhao, J., Shafran, I., Griffiths, T. L., Cao, Y., & Narasimhan, K. (2023). **Tree of thoughts: Deliberate problem solving with large language models**. *NeurIPS 2023*.

[12] Wei, J., Wang, X., Schuurmans, D., Bosma, M., Ichter, B., Xia, F., Chi, E. H., Le, Q. V., & Zhou, D. (2022). **Chain-of-thought prompting elicits reasoning in large language models**. *NeurIPS 2022*.

[13] Jimenez, C. E., Yang, J., Wettig, A., Yao, S., Pei, K., Press, O., & Narasimhan, K. (2024). **SWE-bench: Can language models resolve real-world GitHub issues?**. *ICLR 2024*.

[14] Liu, X., Yu, H., Zhang, H., Xu, Y., Lei, X., Lai, H., et al. (2024). **AgentBench: Evaluating LLMs as agents**. *ICLR 2024*. arXiv:2308.03688.

[15] Zhou, S., Xu, F. F., Zhu, H., Zhou, X., Lo, R., Sridhar, A., et al. (2024). **WebArena: A realistic web environment for building autonomous agents**. *ICLR 2024*.

[16] Mialon, G., Fourrier, C., Swift, C., Wolf, T., LeCun, Y., & Scialom, T. (2023). **GAIA: A benchmark for general AI assistants**. arXiv:2311.12983.

[17] Xie, T., Zhang, D., Chen, J., Li, X., Zhao, S., Cao, R., et al. (2024). **OSWorld: Benchmarking multimodal agents for open-ended tasks in real computer environments**. *NeurIPS 2024 Datasets and Benchmarks Track*. arXiv:2404.07972.

[18] Yao, S., Shinn, N., Razavi, P., & Narasimhan, K. (2024). **τ-bench: A benchmark for tool-agent-user interaction in real-world domains**. arXiv:2406.12045.

## Standard LLM benchmarks (for context)

[19] Hendrycks, D., Burns, C., Basart, S., Zou, A., Mazeika, M., Song, D., & Steinhardt, J. (2021). **Measuring massive multitask language understanding (MMLU)**. *ICLR 2021*.

[20] Cobbe, K., Kosaraju, V., Bavarian, M., Chen, M., Jun, H., Kaiser, L., et al. (2021). **Training verifiers to solve math word problems (GSM8K)**. arXiv:2110.14168.

[21] Chen, M., Tworek, J., Jun, H., Yuan, Q., Pinto, H. P. de O., Kaplan, J., et al. (2021). **Evaluating large language models trained on code (HumanEval)**. arXiv:2107.03374.

## Scaling, distillation, reasoning

[22] Hoffmann, J., Borgeaud, S., Mensch, A., Buchatskaya, E., Cai, T., Rutherford, E., et al. (2022). **Training compute-optimal large language models** (Chinchilla). *NeurIPS 2022*. arXiv:2203.15556.

[23] Hinton, G., Vinyals, O., & Dean, J. (2015). **Distilling the knowledge in a neural network**. *NIPS 2014 Deep Learning Workshop*. arXiv:1503.02531.

[24] Devvrit, Kudugunta, S., Kusupati, A., Dettmers, T., Chen, K., Dhillon, I., Tsvetkov, Y., Hajishirzi, H., Kakade, S., Farhadi, A., & Jain, P. (2024). **MatFormer: Nested transformer for elastic inference**. *NeurIPS 2024*. arXiv:2310.07707.

[25] Jiang, A. Q., Sablayrolles, A., Roux, A., Mensch, A., Savary, B., Bamford, C., et al. (2024). **Mixtral of experts**. arXiv:2401.04088.

## Models used in this paper (technical reports / model cards)

[26] Qwen Team, Alibaba. (2025). **Qwen3 Technical Report** (referenced as the qwen3.5 family in this paper, following the LM Studio runtime identifier convention). arXiv:2505.09388.

[27] Google DeepMind. (2026). **Gemma 4 model family** (E2B / E4B MatFormer thinking variants; 26 B-A4B MoE; 31 B Dense), released 2026-04-02. <https://deepmind.google/models/gemma/gemma-4/>

[28] Zhipu AI / GLM Team. (2025). **GLM-4.5: Agentic, Reasoning, and Coding (ARC) Foundation Models** (355 B total / 32 B active MoE). arXiv:2508.06471.

[29] NVIDIA. (2025). **NVIDIA-Nemotron-3-Nano-4B model card** — hybrid Mamba2-Transformer architecture, pruned and distilled from Nemotron Nano 9B v2 via the Nemotron Elastic framework. <https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF>

[30] Mistral AI. (2025). **Ministral 3 model family** (3 B / 8 B / 14 B; Base / Instruct / Reasoning variants), released December 2025. <https://mistral.ai/news/mistral-3>

[31] OpenAI. (2025). **gpt-oss-120b & gpt-oss-20b Model Card**. arXiv:2508.10925. <https://openai.com/index/gpt-oss-model-card/>

## Protocols

[32] Anthropic. (2024). **Model Context Protocol (MCP) specification**. <https://modelcontextprotocol.io/specification/latest>

[33] Google. (2025). **Agent2Agent (A2A) protocol specification**. Announced April 9, 2025 at Google Cloud Next; donated to the Linux Foundation June 2025. <https://a2a-protocol.org/latest/specification/>

## Compliance and robustness

[34] European Parliament & Council. (2024). **Regulation (EU) 2024/1689 on Artificial Intelligence (AI Act)**. <https://eur-lex.europa.eu/eli/reg/2024/1689/oj>

[35] Greshake, K., Abdelnabi, S., Mishra, S., Endres, C., Holz, T., & Fritz, M. (2023). **Not what you've signed up for: Compromising real-world LLM-integrated applications with indirect prompt injection**. *AISec '23 — ACM Workshop on Artificial Intelligence and Security*.

## Statistical methods

[36] Wilson, E. B. (1927). **Probable inference, the law of succession, and statistical inference**. *Journal of the American Statistical Association*, 22(158), 209–212.

[37] Newcombe, R. G. (1998). **Interval estimation for the difference between independent proportions: comparison of eleven methods**. *Statistics in Medicine*, 17(8), 873–890.

## Concurrent work on LLM-agent reliability / chaos (added 2026-05-12 deep-research pass)

[38] Gupta, A. (2026). **ReliabilityBench: Evaluating LLM Agent Reliability Under Production-Like Stress Conditions**. arXiv:2601.06112 (January 3, 2026). Concurrent with the present paper: chaos-engineering-style fault injection at the LLM tool boundary (timeouts, rate limits, partial responses, schema drift) across 2 frontier APIs and 2 architectures over 1,280 episodes.

[39] Wang, A., Hager, S., Asija, A., Khashabi, D., & Andrews, N. (2025). **Hell or High Water: Evaluating Agentic Recovery from External Failures**. *COLM 2025*. arXiv:2508.11027. Benchmarks agent recovery when functions disappear or fail mid-trajectory.

[40] Wang, R., Chen, Y., Wang, Y., Wu, C., Fang, J., Cai, X., Gu, Q., Su, H., Zhang, A., Wang, X., Cai, X., & Chua, T.-S. (2026). **AgentNoiseBench: Benchmarking Robustness of Tool-Using LLM Agents Under Noisy Condition**. arXiv:2602.11348 (February 2026). Categorises noise into user-noise and tool-noise; complements our fault-rate-per-call framing.

## Independent observation of the inverted-U / hump shape

[41] Khan, I. (2025). **You Don't Need Prompt Engineering Anymore: The Prompting Inversion**. arXiv:2510.22251 (October 25, 2025). Reports an inverted-U pattern: "Sculpting" prompting peaks on gpt-4o (+9 pp vs zero-shot) and collapses to parity on gpt-5 — the same Guardrail-to-Handcuff transition we hypothesise in §4.2(a).

## EU AI Act robustness evidence (Art. 15 / Art. 55)

[42] Bueno Momcilovic, T., Buesser, B., Zizzo, G., Purcell, M., & Balta, D. (2024). **Towards Assuring EU AI Act Compliance and Adversarial Robustness of LLMs**. arXiv:2410.05306 (October 4, 2024).

[43] Nolte, H., Rateike, M., & Finck, M. (2025). **Robustness and Cybersecurity in the EU Artificial Intelligence Act**. *FAccT 2025 — ACM Conference on Fairness, Accountability, and Transparency*. arXiv:2502.16184.

## Distillation and robustness (historical anchor)

[44] Papernot, N., McDaniel, P., Wu, X., Jha, S., & Swami, A. (2016). **Distillation as a Defense to Adversarial Perturbations against Deep Neural Networks**. *IEEE Symposium on Security and Privacy 2016*. arXiv:1511.04508.
