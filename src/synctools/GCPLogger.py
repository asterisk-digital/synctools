import json
import logging


# Returns a dict that can be unpacked with ** in a logging.* call so GCP can parse it
def logdata(data):
    return {"extra": {"data": data}}


class GCPLogger(logging.Handler):
    def emit(self, record):
        log_data = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "data": record.__dict__.get("data", {}),
        }

        print(json.dumps(log_data))
