import os
from dotenv import load_dotenv
load_dotenv()

from core.chains.llm import GeminiLLM, SuperGemini, get_parsed_response

SECRET_KEY = os.getenv("GEMINI")

# llm = GeminiLLM(SECRET_KEY)
# prompt = "gimme a recipie for shortbread cookies in json format with ingredients and steps"
# res = get_parsed_response(llm, prompt)
# print(res)

llm = SuperGemini()
prompt = "What are the top 3 most populous cities in the world? Respond in JSON format with a list of 3 city names and their populations."
response = get_parsed_response(llm, prompt)