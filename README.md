# LogNexus

**LogNexus: From Raw Streams to Operational Insights via Neural-Symbolic Event Reconstruction**

![framework](./code_readme.assets/framework.png)

## 📖 Introduction

**LogNexus** is a hybrid **neural-symbolic framework** designed to resolve the conflict between semantic accuracy and operational efficiency in log event reconstruction. It transforms raw, interleaved log streams into actionable operational insights through a coarse-to-fine pipeline:

1.  **Neural-to-Symbolic Synthesis (Phase I):** An LLM acts as a code synthesis agent, generating deterministic, executable partitioning rules from diversity-sampled contexts. This decouples expensive reasoning from high-volume processing.
2.  **Log Representation Learning & Refinement (Phase II):** We introduce a specialized **Bi-Directional Mamba (Bi-Mamba)** encoder. This model captures long-range dependencies with linear computational complexity ($O(L)$), refining coarse partitions into precise event instances.
3.  **Dynamic Knowledge Base Construction (Phase III):** Refined events are incrementally clustered into an operational knowledge base, enabling real-time analysis and summarization.

Extensive evaluations on **OpenSSH**, **Linux**, and **Apache** datasets demonstrate that LogNexus achieves state-of-the-art performance (e.g., **ARI 1.0000** on OpenSSH), significantly outperforming statistical baselines and direct LLM approaches while reducing token costs by orders of magnitude.

## 📂 File Structure

```plaintext
LogNexus/
├── data/                   # Dataset storage (Raw logs & Ground truth)
├── utils/                  # Utility functions (Config, LLM wrappers)
├── data_preprocessing/     # Preprocessing scripts (Parsing, Encoding)
├── event_detector/         # Phase I: Rule synthesis & Coarse partitioning
├── event_refinement/       # Phase II: Bi-Mamba training & Event refinement
├── knowledge_base/         # Phase III: Dynamic clustering & KB construction
├── generated_processors/   # Synthesized Python scripts from Phase I
├── benchmark/              # Baseline methods implementation
├── ablation_experiments/   # Scripts for ablation studies
└── results/                # Evaluation metrics & Output logs
```

**Note:** The `cache/` directory is not included in this repository. It will be created automatically when you first run the code to store model checkpoints and encoder artifacts.

## 🛠️ Dependencies

LogNexus has been validated on **Ubuntu 20.04** with **Python 3.12.0**.

1. **Install Core Requirements:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Configure LLM API:**
   Modify `utils/config.py` to set up your LLM provider (e.g., OpenAI, Gemini, DeepSeek).

   ```python
   # utils/config.py
   self.llm_api_key = os.getenv("LLM_PROXY_API_KEY", "your_actual_api_key")
   self.llm_model_name = "gemini-2.5-pro" # or gpt-4o, deepseek-chat
   self.llm_base_url = "https://api.example.com/v1"
   ```

## 📊 Datasets

We utilize datasets from [LogHub-2.0](https://github.com/logpai/Loghub-2.0). Due to licensing, please download the raw data manually and place it in the `./data` directory.

### Preparation Steps

1. Download `Apache.zip`, `Linux.zip`, and `OpenSSH.zip` from [Zenodo](https://zenodo.org/records/8275861).

2. Extract them into the `./data` folder.

3. Run the splitting script to generate training/testing sets according to our chronological protocol (6:1:3 ratio):

   ```bash
   cd ./data/
   python ./split_dataset.py
   ```

### Directory Layout (Example: Linux)

After splitting, the `./data` directory should look like this:

*   `Linux_train.log`: First 60% (Used for Sampling & Training)
*   `Linux_online_eval.log`: Middle 10% (Temporal Buffer)
*   `Linux_test.log`: Last 30% (Testing)
*   `Linux_test_label.log`: Ground truth labels for testing (Annotated via our guideline-based protocol).

## 🚀 Usage & Reproduction

### 1. Quick Start (Run LogNexus)

To run the full LogNexus pipeline on a specific dataset (default: Linux):

1. Set the target dataset in `utils/config.py` or via environment variable.

2. Run the main script:

   ```bash
   # This runs the 'full_model' mode by default
   cd ./ablation_experiments/
   python ./run_ablation.py
   ```

   *Note: If a synthesized processor does not exist in `./generated_processors`, the system will automatically trigger the LLM to generate one.*

### 2. Ablation Studies

To reproduce the ablation study results presented in the paper (Table 4 & 6), use the provided shell script. This will run 5 iterations for stability analysis.

1. Edit `ablation_experiments/run_ablation.sh` to select the dataset:

   ```bash
   export DATASET_NAME="Linux"
   ```

2. Execute the script:

   ```bash
   cd ./ablation_experiments/
   bash ./run_ablation.sh
   ```

3. Generate the summary report (CSV):

   ```bash
   cd ./generated_processors/
   python ./eval.py
   ```

   *Output Example:*

   ```csv
   Mode, ARI, NMI, Inference Time (ms), ...
   full_model, 0.9190±0.02, 0.9854±0.006, 409.54, ...
   no_refinement, 0.8869±0.06, 0.9722±0.019, 0.00, ...
   ```

### 3. Knowledge Base Evaluation

To evaluate the quality of the constructed Operational Knowledge Base (Phase III):

```bash
python ./knowledge_base/kb_evaluator.py
```

*   **Metrics:** Event Type Discovery Accuracy (ETDA), Event Classification Accuracy (ECA).
*   **Note:** If you wish to rebuild the KB from scratch, run `knowledge_base_builder.py`. *Warning: This requires re-annotating the semantic correctness of newly discovered event types.*

### 4. Baselines Comparison

To run baseline methods (DeepCASE, TF-IDF, Direct LLM, etc.):

```bash
cd ./benchmark/
python ./benchmark/run_benchmarks.py --methods llm_knowledge deepcase traditional
```

*   Available methods: `traditional`, `deepcase`, `pretrained`, `llm_naive`, `llm_knowledge`, `llm_cot`.

## 🔧 Troubleshooting

### Common Issues

#### 1. Missing cache directory
The `cache/` directory is not included in the repository. It will be automatically created when you run the code for the first time.

#### 2. LLM API Configuration
If you encounter LLM API errors:
- Ensure your API key is correctly set in `utils/config.py` or as an environment variable `LLM_PROXY_API_KEY`
- Verify your API endpoint is accessible
- Check that your chosen model name is supported by your API provider

Example environment variable setup:
```bash
export LLM_PROXY_API_KEY="your_api_key_here"
export DATASET_NAME="Linux"  # or "OpenSSH", "Apache"
```

#### 3. Missing Dataset Files
If you see errors about missing log files:
- Ensure you've downloaded and extracted the datasets from Zenodo
- Run the `split_dataset.py` script to generate train/test splits
- Verify the dataset files exist in `./data/[DATASET_NAME]/`

#### 4. CUDA/GPU Issues
If CUDA is not available or you encounter GPU errors:
- The code will automatically fall back to CPU
- You can manually set the device in `utils/config.py` by modifying the `device` parameter

#### 5. Import Errors
If you encounter module import errors:
- Ensure you've installed all requirements: `pip install -r requirements.txt`
- Some dependencies (like `mamba-ssm`) may require specific CUDA versions
- For CPU-only installation, you may need to modify the torch installation

## 🎯 Quick Start Checklist

Before running LogNexus for the first time:

- [ ] Downloaded and extracted datasets from Zenodo
- [ ] Placed datasets in `./data/` directory
- [ ] Run `python ./data/split_dataset.py` to generate splits
- [ ] Installed all dependencies via `pip install -r requirements.txt`
- [ ] Configured LLM API settings in `utils/config.py` or environment variables
- [ ] Set `DATASET_NAME` environment variable (default: "Linux")

## 📝 Citation

If you use LogNexus in your research, please cite our paper:

```bibtex
@article{lognexus2024,
  title={LOGNEXUS: A Neural-Symbolic Framework for Security Event Reconstruction from Log Streams},
  author={Your Name et al.},
  journal={arXiv preprint},
  year={2026}
}
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📧 Contact

For questions or issues, please open an issue on GitHub or contact the authors.
