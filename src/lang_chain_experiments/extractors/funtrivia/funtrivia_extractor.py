#!/usr/bin/env python3
import re
import uuid
import json
import httpx
import asyncio
import hashlib
import argparse

from bs4 import BeautifulSoup


class FuntriviaExtractor:
    @staticmethod
    def __extract_question_answer(soup: BeautifulSoup, uuid) -> dict|None:
        # Find the first "b" tag that contains the question
        question_tag = soup.find('b')
        if not question_tag:
            return None

        # Extract the question text
        question = question_tag.get_text(strip=True)
        match = re.match(r'^\d+\.\s*(.*)', question)
        question = match.group(1).strip()

        # Find the "div" tag with class "extrainfo" that contains the answer
        answer_div = soup.find('div', class_='extrainfo')
        if not answer_div:
            return None

        # Extract the answer text
        answer_parts = []
        for child in answer_div.children:
            if child.name == 'span':
                answer_parts.append(child.get_text(strip=True))
            elif isinstance(child, str):
                answer_parts.append(child.strip())
        answer = '\n'.join(answer_parts).replace("Answer:\n", "")

        # Return the result as a dictionary
        return {"q": question, "a": answer, "uuid": uuid}

    def __extract_all_questions_answers(self, soup: BeautifulSoup, uuid: str) -> [dict]:
        # Find the div with class "quizheading" and text that starts with "Quiz Answer Key"
        quiz_heading = soup.find('div', class_='quizheading', string=lambda text: text and text.startswith('Quiz Answer Key'))
        if not quiz_heading:
            return []

        # Find the parent of the quiz heading
        parent_div = quiz_heading.find_parent()
        if not parent_div:
            return []

        # Find all child divs of the parent that contain questions and answers
        question_answer_divs = parent_div.find_all('div', recursive=False)

        # Extract questions and answers from each div and store them in an array of dictionaries
        result = []
        for (i, div) in enumerate(question_answer_divs):
            question_answer = self.__extract_question_answer(div, uuid + str(i))
            if question_answer:
                result.append(question_answer)

        return result

    async def __fetch_url(self, client, url):
        try:
            response = await client.get(url)
            return self.__fetch_questions_answers_from_response(url, response)
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    async def fetch_questions_answers_from_urls(self, urls):
        async with httpx.AsyncClient() as client:
            tasks = [self.__fetch_url(client, url) for url in urls]
            responses = await asyncio.gather(*tasks)
        return responses

    async def fetch_questions_answers_from_url(self, url: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await self.__fetch_url(client, url)
        return response

    @staticmethod
    def __generate_uuid_from_seed(seed):
        # Hash the seed value using SHA-1
        hash_value = hashlib.sha1(seed.encode('utf-8')).hexdigest()

        # Convert the first 16 bytes of the hash to a UUID
        return str(uuid.UUID(hash_value[:32]))

    def __fetch_questions_answers_from_response(self, url, response) -> dict:
        # Check if the request was successful (status code 200)
        if response.status_code != 200:
            print(f"Failed to fetch URL: {url} (status code: {response.status_code})")
            return {}

        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        uuid = self.__generate_uuid_from_seed(url)
        title = soup.find('h1').text

        # Extract questions and answers using the extract_all_questions_answers method
        result = self.__extract_all_questions_answers(soup, uuid)

        return {'url': url, 'title': title, 'uuid': uuid, 'content': result}


async def main():
    parser = argparse.ArgumentParser(description='Fetch and extract questions and answers from a quiz URL.')
    parser.add_argument('--out', help='The path to the output JSON file.', default='./')
    parser.add_argument('--batch', type=int, help='The path to the output JSON file.', default=3)
    parser.add_argument('urls', type=str, nargs='+', help='One or more URLs of the quiz page(s).')
    args = parser.parse_args()

    batch_size = args.batch

    cls = FuntriviaExtractor()

    for i in range(0, len(args.urls), batch_size):
        batch = args.urls[i:i + batch_size]
        responses = await cls.fetch_questions_answers_from_urls(batch)
        # Process the responses here, if needed
        for response in responses:
            if response is not None:
                url = response['url']
                output_filename = (args.out + url.split("/")[-1]).replace(".html", ".json")
                with open(output_filename, 'w') as outfile:
                    json.dump(response, outfile)
                    print(f"Questions and answers have been successfully extracted and saved to {output_filename}")


if __name__ == '__main__':
    asyncio.run(main())
