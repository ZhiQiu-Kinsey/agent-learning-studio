"""Print the names of the environment variables this process can see, as JSON.

Names only, never values: the lesson uses it to show which variables a command started
by the platform inherits, without writing anything secret into the run record.
"""
import json
import os

print(json.dumps({"names": sorted(os.environ)}))
