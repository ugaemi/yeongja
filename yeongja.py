import json
import os
import random
import time
import re

from urllib.request import urlopen
from urllib import parse
from bs4 import BeautifulSoup
from slackclient import SlackClient

from config import SEARCH_URL, DETAIL_URL
from custom_error import CrawlingError

# 슬랙 클라이언트를 인스턴스화
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))

# yeongja의 user ID : 값은 봇이 시작된 후에 할당됨
yeongja_id = None

RTM_READ_DELAY = 1  # RTM에서 읽기까지 1초 지연
CALL_COMMAND = re.compile('맛집*')
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"


def parse_bot_commands(slack_events):
    """
        명령을 찾기 위해 Slack RTM API에서 오는 이벤트 목록을 구문 분석합니다.
        명령을 찾으면 명령과 채널의 튜플을 반환합니다.
        명령이 없으면 None, None을 반환합니다.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            if user_id == yeongja_id:
                return message, event["channel"]
    return None, None


def parse_direct_mention(message_text):
    """
        메시지 텍스트에서 시작 부분에 나오는 언급을 찾습니다.
        언급 된 사용자 ID를 리턴합니다. 직접 언급이 없으면 None을 반환합니다.
    """
    matches = re.search(MENTION_REGEX, message_text)
    # 첫 번째 그룹에는 사용자 이름이 포함되고 두 번째 그룹에는 나머지 메시지가 포함됨
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)


def get_data_from_naver(query):
    """
        네이버에서 현재 위치 기반 맛집 데이터를 가져옵니다.
    """
    search_url = SEARCH_URL + parse.quote(query)
    html = urlopen(search_url)
    soup = BeautifulSoup(html, "html.parser")
    return soup


def get_data_from_soup(query):
    """
        크롤링하여 가져온 맛집 데이터를 정재합니다.
    """
    try:
        soup = get_data_from_naver(query)
    except CrawlingError:
        raise
    script_text = soup.findAll('script')[2].get_text()
    relevant = script_text[script_text.index('=') + 1:]
    data = json.loads(relevant)
    return data


def get_res_list(query):
    """
        상위 50개 맛집 리스트를 뽑습니다.
    """
    data = get_data_from_soup(query)
    res_list = data['businesses']['[query:' + query + ']']['items'][:30]
    return res_list


def handle_command(command, channel):
    """
        bot 명령을 실행합니다.
    """
    # 기본 응답은 사용자를 위한 도움말 텍스트
    default_response = "저는 맛집 추천 봇 영자입니다. '지역명 맛집'을 찾아달라고 말해주세요!"

    # 주어진 명령을 찾아서 실행하고 응답으로 채움
    response = None

    if CALL_COMMAND.search(command):
        location = command.split('맛집')[0]
        query = location + " 맛집"
        res_list = get_res_list(query)
        res = random.choice(res_list)
        detail_url = DETAIL_URL + res['id']
        response = "'" + res['name'] + "'" + "을(를) 추천합니다.\n자세히 보기:" + detail_url

    # 응답을 채널에 다시 보냄
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response or default_response
    )


if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("이영자봇 연결 및 실행 중!")
        flag = False
        # Web API 함수 `auth.test`로부터 봇의 user ID를 읽음
        yeongja_id = slack_client.api_call("auth.test")["user_id"]

        while True:
            command, channel = parse_bot_commands(slack_client.rtm_read())
            if command:
                handle_command(command, channel)
            time.sleep(RTM_READ_DELAY)
    else:
        print("연결에 실패하였습니다. 에러를 확인해주세요.")
