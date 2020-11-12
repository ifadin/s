import base64
import os

from epics.auth import EAuth

u_a = base64.b64decode('NDA1NDM2'.encode()).decode()
u_a_auth = EAuth(os.environ['EP_REF_TOKEN'])
u_b = base64.b64decode('NDIwNzYx'.encode()).decode()
u_b_auth = EAuth(os.environ['EP_REF_TOKEN_B'])