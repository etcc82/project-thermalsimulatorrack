# coolrack

A simulated liquid-cooled server rack you can watch and break.

## Run it

    python3 server.py

Then open http://localhost:8000. Nothing to install: it uses only Python's
standard library (Python 3.9 or newer).

## Files

- `engine.py`  the physics: eight cold plates on one coolant loop
- `server.py`  runs the engine and streams its state to the browser
- `index.html` draws the rack; contains no physics
- `test_engine.py`  checks the engine (run `python3 test_engine.py`)
- `sim.py`  step 1: a single cold plate, plotted with matplotlib

## Honest limits

The hardware numbers are ballparks, not measured values. Cold plate
resistance is fixed (in reality it improves with flow), the controller reads
perfect temperatures (no sensor noise or drift), and total flow ignores how a
real pump responds to resistance in the loop.
