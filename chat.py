import os
import argparse
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True)
    parser.add_argument("--stream", action="store_true")
    args = parser.parse_args()

    messages = [
        {"role": "system", "content": "你是一个简洁的中文助手。"},
        {"role": "user", "content": args.question},
    ]

    if args.stream:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=True,
            timeout=30,
        )
        for chunk in resp:
            delta = chunk.choices[0].delta.content
            if delta:
                print(delta, end="", flush=True)
        print()
    else:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            timeout=30,
        )
        print(resp.choices[0].message.content)


if __name__ == "__main__":
    main()