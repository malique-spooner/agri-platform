# Agri Platform

Version 0 prototype for coordinating agricultural supply pledges between buyers and farmers.

## Setup

Create the SQLite database:

```bash
python database/setup_database.py
```

Generate a synthetic dataset:

```bash
python database/generate_data.py
```

Run the Flask application:

```bash
python app.py
```

Run the tests:

```bash
pytest
```

## Logging

The project uses Python's standard `logging` library for runtime logging.

- Development documentation is kept in `docs/dev_logs.txt`.
- Runtime application logs are written separately to `logs/app.log`.
