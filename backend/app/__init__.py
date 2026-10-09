"""MineMind AI backend package (SIH26009 prototype).

The package is organised as:

* ``app.domain``  - pure data/ML logic (validation, synthetic data, forecasting ...).
* ``app.schemas`` - Pydantic models describing API requests and responses.
* ``app.api``     - FastAPI routers; they contain no business logic.
"""

__version__ = "1.0.0"
