# ATT Plane Group 6

Short setup guide for cloning the project and creating a local `uv` environment.

## 1. Clone the repository

```zsh
git clone https://github.com/davidcarrilloag/attplanegrp6.git
cd attplanegrp6
```

## 2. Create and activate the virtual environment

```zsh
uv venv --python 3.11
source .venv/bin/activate
```

## 3. Install dependencies

The dependency file in this repo is `pyproject.toml`.

Install the app dependencies:

```zsh
uv pip install -e .
```

For notebook/Jupyter dependencies too:

```zsh
uv pip install -e ".[dev]"
```

## 4. Run the Streamlit app

```zsh
streamlit run app.py
```

If `uv` is not installed yet:

```zsh
curl -LsSf https://astral.sh/uv/install.sh | sh
```
