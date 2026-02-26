[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/x-plug-osworld-mcp-badge.png)](https://mseep.ai/app/x-plug-osworld-mcp)

# OSWorld-MCP: Benchmarking MCP Tool Invocation in Computer-Use Agents

## 🔔 Updates
**2025-10-28:** We released our paper and project page! 🎉 

📄 [Read the Paper](https://arxiv.org/abs/2510.24563) &nbsp;|&nbsp; 🌐 [Visit the Project Page](https://osworld-mcp.github.io)

---

## 📑 Overview & Key Highlights

OSWorld-MCP is a comprehensive and fair benchmark for evaluating computer-use agents in real-world scenarios.  
It jointly measures **Model Context Protocol (MCP)** tool invocation capabilities, **graphical user interface (GUI)** operation skills, and **decision-making** performance.  
Designed as an extension of **OSWorld**, it significantly improves realism, balance, and comparability in evaluation.

**Key Features & Findings**
- **158 validated MCP tools**, spanning **7 common applications** (LibreOffice Writer, Calc, Impress, VS Code, Google Chrome, VLC, OS utilities). Among them, **25 distractor tools** for robustness testing
- **250 tool-beneficial tasks** → 69% of benchmark tasks benefit from MCP tools
- Multi-round tool invocation possible, posing real decision-making challenges
- **MCP tools boost model accuracy & efficiency** — e.g., OpenAI o3: 8.3% → 20.4% (15 steps)
- Highest observed Tool Invocation Rate (**TIR**) = 36.3% (Claude-4-Sonnet, 50 steps) → indicating ample room for improvement
- MCP tools improve agent metrics
- Higher tool invocation correlates with higher accuracy
- Combining tools introduces significant challenges



**Architecture Overview**  

![OSWorld-MCP Architecture](images/architecture.png)  
*Figure: OSWorld-MCP evaluation framework integrating GUI actions and MCP tool invocations.*

---

## ⚙️ Installation & Usage

### 1️⃣ Preparation: Code Setup
```bash
# Clone OSWorld base repo
git clone https://github.com/xlang-ai/OSWorld.git

# Clone OSWorld-MCP
git clone https://github.com/X-PLUG/OSWorld-MCP.git
```
Integrate **OSWorld-MCP** files into OSWorld to enable MCP support.

---

### 2️⃣ Preparation: Docker Environment
1. Copy MCP files into `/home` inside Docker:
```
/home/
└── mcp_server/
└── osworld_mcp_client.py
```
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Install [Node.js](https://nodejs.org/en/download/)  
4. Launch MCP server:
```bash
cd mcp_server
bash debug_server.sh
```
A successful launch opens the local MCP debug UI in your browser.

---

### 3️⃣ Running Evaluation
Example: Evaluate **Claude 4 Sonnet** (15 steps):
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

## 📐 Key Metrics

1. **Task Accuracy (Acc)** — % of tasks successfully completed.
2. **Tool Invocation Rate (TIR)** — correct decisions to use a tool or not.
3. **Average Completion Steps (ACS)** — average number of actions per completed task.

---

## 📊 Leaderboard (Sorted by Accuracy)

🔗 **Live Leaderboard:** [osworld-mcp.github.io](https://osworld-mcp.github.io)

**Max Steps: 15**

| Model / Agent        | Acc | TIR | ACS |
|----------------------|----------|-----------------------------|-----------------------------|
| Agent-S2.5           | 42.1     | 30.0                        | 10.0                        |
| Claude-4-Sonnet      | 35.3     | 30.0                        | 10.4                        |
| Seed1.5-VL           | 32.0     | 25.1                        | 10.2                        |
| Qwen3-VL             | 31.3     | 24.5                        | 10.5                        |
| Gemini-2.5-Pro       | 20.5     | 16.8                        | 11.4                        |
| OpenAI o3            | 20.4     | 16.7                        | 11.6                        |
| Qwen2.5-VL           | 15.8     | 13.1                        | 13.5                        |

**Max Steps: 50**

| Model / Agent        | Acc | TIR   | ACS   |
|----------------------|----------|-------|-------|
| Agent-S2.5           | 49.5     | 35.3  | 17.0  |
| Claude-4-Sonnet      | 43.3     | 36.6  | 20.1  |
| Qwen3-VL             | 39.1     | 29.5  | 21.1  |
| Seed1.5-VL           | 38.4     | 29.0  | 23.0  |
| Gemini-2.5-Pro       | 27.2     | 21.5  | 29.7  |
| OpenAI o3            | 25.2     | 21.0  | 32.1  |
| Qwen2.5-VL           | 14.8     | 10.9  | 37.2  |

---

## 📚 Citation

```bibtex
@article{jia2025osworldmcp,
  title={OSWorld-MCP: Benchmarking MCP Tool Invocation in Computer-Use Agents},
  author={Jia, Hongrui and Liao, Jitong and Zhang, Xi and Xu, Haiyang and Xie, Tianbao and Jiang, Chaoya and Yan, Ming and Liu, Si and Ye, Wei and Huang, Fei},
  year={2025},
  journal={arXiv preprint arXiv:2510.24563}
}
```