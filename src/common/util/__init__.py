from dotenv import load_dotenv
import os
import traceback
import sys

from src.common.util import errors


class Config:
	def __init__(self):
		# Load environment variables
		load_dotenv()

		# Set properties
		for key, datatype, default in [
			("DEVELOPMENT", bool, False),
			("IP_HEADER", str, None),
			("IPHUB_KEY", str, None),
			("BLOCK_PROXIES", bool, False),
			("HOST", str, "0.0.0.0"),
			("API_PORT", int, 3000),
			("CL3_PORT", int, 3001),
			("DB_URI", str, "mongodb://127.0.0.1:27017"),
			("DB_NAME", str, "meowerserver"),
			("REDIS_HOST", str, "127.0.0.1"),
			("REDIS_PORT", int, 6379),
			("REDIS_DB", int, 0),
			("REDIS_PASSWORD", str, None)
		]:
			env_vars = {}
			if key in os.environ:
				if datatype is bool:
					env_vars[key] = (os.environ[key] == "true")
				else:
					env_vars[key] = datatype(os.environ[key])
			setattr(self, key.lower(), env_vars.get(key.upper(), default))


def display_startup():
	print(f"Meower -- {version} ({build_time})")


def full_stack():
		exc = sys.exc_info()[0]
		if exc is not None:
			f = sys.exc_info()[-1].tb_frame.f_back
			stack = traceback.extract_stack(f)
		else:
			stack = traceback.extract_stack()[:-1]
		trc = 'Traceback (most recent call last):\n'
		stackstr = trc + ''.join(traceback.format_list(stack))
		if exc is not None:
			stackstr += '  ' + traceback.format_exc().lstrip(trc)
		return stackstr


def validate(data: dict, expected: dict[str, tuple[type, int, int]], optional: list[str] = []):
	if (not isinstance(data, dict)) and (set(expected.keys()) != set(optional)):
		raise errors.InvalidDatatype

	for key, (datatype, min, max) in expected.items():
		if key in data:
			if datatype and (not isinstance(data[key], datatype)):
				raise errors.InvalidDatatype
			
			if datatype == str:
				if min and (len(data[key]) < min):
					raise errors.TooShort

				if max and (len(data[key]) > max):
					raise errors.TooLarge
			elif datatype == int:
				if min and (data[key] < min):
					raise errors.InvalidSyntax
				
				if max and (data[key] > max):
					raise errors.InvalidSyntax
		elif key not in optional:
			raise errors.InvalidSyntax


config = Config()
version = "0.5.0-beta"
build_time = 1683123390
