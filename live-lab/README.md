# RootTrace Live Lab — Sample Microservice

This is an ordinary, standalone FastAPI e-commerce and order processing service.
It runs as an independent child process monitored by RootTrace.

## Structure
- `app/main.py`: FastAPI server running on port 8001
- `app/services.py`: Business logic for order calculations, discount validation, and inventory
- `tests/test_api.py`: Baseline regression tests

## Manual Demonstration Workflow
1. Start RootTrace and launch the Live Lab application from the Live Debug Console.
2. The service starts on `http://127.0.0.1:8001` and its baseline tests pass.
3. During a live demo, edit code in `live-lab/app/services.py` or `live-lab/app/main.py` (e.g. introduce a ZeroDivisionError, syntax error, or faulty discount calculation).
4. RootTrace detects the failure through real health probes, test runs, or error logs, performs evidence-grounded diagnosis, and presents a verified candidate patch for approval.
