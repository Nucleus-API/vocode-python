import logging
import os
from fastapi import FastAPI
from vocode.streaming.models.telephony import TwilioConfig
from pyngrok import ngrok
from vocode.streaming.telephony.config_manager.redis_config_manager import (
    RedisConfigManager,
)
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.telephony.server.base import (
    InboundCallConfig,
    TelephonyServer,
)

from speller_agent import (SpellerAgentFactory, SpellerAgentConfig)
import sys

# if running from python, this will load the local .env
# docker-compose will load the .env file by itself
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(docs_url=None)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_manager = RedisConfigManager()

BASE_URL = os.getenv("BASE_URL")

if not BASE_URL:
    ngrok_auth = os.environ.get("NGROK_AUTH_TOKEN")
    if ngrok_auth is not None:
        ngrok.set_auth_token(ngrok_auth)
    port = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else 3000

    # Open a ngrok tunnel to the dev server
    BASE_URL = ngrok.connect(port).public_url.replace("https://", "")
    logger.info('ngrok tunnel "{}" -> "http://127.0.0.1:{}"'.format(BASE_URL, port))

if not BASE_URL:
    raise ValueError("BASE_URL must be set in environment if not using pyngrok")

telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[
        InboundCallConfig(
            url="/inbound_call",
            agent_config=ChatGPTAgentConfig(
                initial_message=BaseMessage(text="Hi! This is Heather from Heat and AC Solutions. How can I help you today?"),
                prompt_preamble="HavYou are a world class, human, customer service agent for Heat and AC Solutions - your job is to answer questions and make the customer feel happy and taken care of. say the scripted answers provided in the FAQ doc: FAQ_DOC_START Q: I am having issues with my AC/HVAC unit. A: I am so sorry to hear about [customer's question/objection]. Yes, we can help with that. Our regular hours service call is $79, which includes an on site inspection to identify the root cause of the problem. To book the appointment, I have sent you booking link to your cell phone. intent: regular_hours Q: I am looking for installation of a new furnace/heat pump. A: Sure, we provide free in-person visits for an estimate on installation of [customer's system]. I have texted you the link to book the appointment. action: installation_notification. FAQ_DOC_END . Use only FAQ doc to answer questions: - Do not provide any answers that deviate from your FAQ doc (do not lengthen the answers more than the examples given): - If you don't know the answer to a question the customer asks, just say - You know I’m not sure I’ll make sure I escalate that to someone on the team who does know and they will get back to you. intent: human_attention - Don't try to make up an answer. and don't say more than the FAQ examples states. Please also return the intent classification in JSON format. Finally, don’t end the call until all of their concerns are handled.",
                generate_responses=True,
            ),
            twilio_config=TwilioConfig(
                account_sid=os.environ["TWILIO_ACCOUNT_SID"],
                auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            ),
        )
    ],
    agent_factory=SpellerAgentFactory(),
    logger=logger,
)

app.include_router(telephony_server.get_router())
