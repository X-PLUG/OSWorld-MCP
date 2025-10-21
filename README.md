# OSWorld-MCP: Benchmarking MCP Tool Invocation in Computer-Use Agents

**OSWorld-MCP** is a benchmark for evaluating computer-use agents with integrated **MCP tool invocation** and **GUI operations** in real-world scenarios.

- **158 validated MCP tools** across **7 common applications**
- Covers **250 tasks** → **69%** tool-applicable
- Includes **25 distractor tools** for robustness
- Tasks feature **multi-round tool invocation** (up to 4 rounds)

Full paper: [OSWorld-MCP: Benchmarking MCP Tool Invocation in Computer-Use Agents (TODO)](https://arxiv.org/abs/xxxx.xxxxx)

---

## 📊 Leaderboard

### 15 Steps

| Rank | Agent Model     | Accuracy (%) | TIR (%) | ACS  |
| ---- | --------------- | ------------ | ------- | ---- |
| 1    | Agent-S2.5      | **42.8**     | 28.2    | 10.2 |
| 2    | Claude-4-Sonnet | **38.9**     | 31.9    | 10.6 |
| 3    | Seed1.5-VL      | **34.8**     | 24.4    | 10.2 |
| 4    | Gemini-2.5-Pro  | **23.8**     | 19.4    | 11.8 |
| 5    | OpenAI o3       | **22.1**     | 17.4    | 12.1 |
| 6    | Qwen2.5-VL      | **15.1**     | 11.4    | 13.7 |

### 50 Steps

| Rank | Agent Model     | Accuracy (%) | TIR (%) | ACS  |
| ---- | --------------- | ------------ | ------- | ---- |
| 1    | Agent-S2.5      | **51.4**     | 35.2    | 17.4 |
| 2    | Claude-4-Sonnet | **43.8**     | 37.4    | 20.2 |
| 3    | Seed1.5-VL      | **39.5**     | 29.6    | 23.0 |
| 4    | Gemini-2.5-Pro  | **26.9**     | 21.9    | 29.9 |
| 5    | OpenAI o3       | **23.8**     | 20.2    | 32.3 |
| 6    | Qwen2.5-VL      | **13.6**     | 10.0    | 38.4 |

---

## 📥 Installation & Usage

### 1. Preparation: Code

First, clone the original **OSWorld** repository and prepare the Docker image as per its documentation:

```bash
# Clone OSWorld
git clone https://github.com/xlang-ai/OSWorld.git
```

Then, clone **OSWorld-MCP**:

```bash
# Clone OSWorld-MCP
git clone https://github.com/yourname/OSWorld-MCP.git
```

Replace the relevant files from **OSWorld-MCP** into the original OSWorld repository to enable MCP functionality.

---

### 2. Preparation: Docker

- Copy the files and directories in the `mcp` directory into the Docker image, placing them under the `/home` directory.

```
/home/
└── mcp_server/
└── osworld_mcp_client.py
```

- Inside the Docker container, install dependencies to configure the **FastMCP** runtime environment:

```bash
pip install -r requirements.txt
```

- Install Node.js: https://nodejs.org/en/download/
- Start the virtual machine and run:

```bash
cd mcp_server
bash debug_server.sh
```

If the browser launches the local debugging interface successfully, the environment is correctly configured.

---

### 3. Running the Evaluation

Example: Running with **Claude 4 Sonnet** for a 15-step OSWorld evaluation:

```bash
python run_multienv_e2e.py \
    --api_url <your_api_url> \
    --api_key <your_api_key> \
    --model 'claude-sonnet-4-20250514-thinking' \
    --test_all_meta_path 'evaluation_examples/test_all.json' \
    --num_envs 1 \
    --action_space mcp \
    --max_steps 15 \
    --max_trajectory_length 15
```

---

## 📚 Citation

If you use **OSWorld-MCP** in your research, please cite (TODO):

```bibtex
@article{jia2025osworldmcp,
  title={OSWorld-MCP: Benchmarking MCP Tool Invocation in Computer-Use Agents},
  author={Jia, Hongrui and Liao, Jitong and Zhang, Xi and Xu, Haiyang and Xie, Tianbao and Jiang, Chaoya and Yan, Ming and Liu, Si and Ye, Wei and Huang, Fei},
  year={2025},
  journal={arXiv preprint arXiv:xxxx.xxxxx}
}
```
