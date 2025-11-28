# CSC458 Programming Assignment 2

### Instructions

To run the program, execute the following command in your terminal:

```bash
./scripts/clean.sh && ./scripts/setup.sh

./scripts/run.sh
```

> I needed to run both with `sudo` to get the necessary permission for both `clean.sh` and `run.sh`, so if you encounter permission issues, try:

```bash
sudo ./scripts/run.sh
```

This will run the program with the default parameters specified in `./scripts/run.sh`.

Two directories will be created in the root directory:

- `bb-q20`: Contains the raw output and plots from running bufferbloat with q=20.
- `bb-q100`: Contains the raw output and plots from running bufferbloat with q=100.

The `saved_plots` directory contains plots and raw data from a previous run of the program.
