"""이유하 릴스 1편을 인스타에 올린다.

사용: python publish.py <발행대기 안의 폴더 이름>
폴더 안에 영상 파일(.mp4) 1개와 게시글.txt 가 있어야 한다.
열쇠(IG_TOKEN)와 계정 번호(IG_USER_ID)는 깃허브 비밀 값/환경 값으로만 받는다.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://graph.instagram.com/v23.0"
TOKEN = os.environ["IG_TOKEN"]
USER_ID = os.environ["IG_USER_ID"]
AI_NOTE = "이 영상은 AI로 만든 인물이 나와요."


def call(method, url, params=None, data=None, headers=None):
    if params and method == "POST" and data is None:
        # 인스타는 POST 값을 주소 뒤가 아니라 본문으로 받아야 upload_type 등을 읽는다
        data = urllib.parse.urlencode(params).encode("utf-8")
        headers = {**(headers or {}), "Content-Type": "application/x-www-form-urlencoded"}
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace").replace(TOKEN, "***")
        sys.exit(f"인스타 오류 {e.code}: {body}")


def main():
    folder = Path("발행대기") / sys.argv[1]
    videos = list(folder.glob("*.mp4"))
    if len(videos) != 1:
        sys.exit(f"{folder} 안에 mp4가 1개여야 합니다 (지금 {len(videos)}개)")
    video = videos[0]
    caption = (folder / "게시글.txt").read_text(encoding="utf-8").strip()
    # API로는 AI 라벨을 켤 수 없어서 게시글에 AI 안내 한 줄을 넣는다 (해시태그 구분선 "-" 앞)
    if AI_NOTE not in caption:
        lines = caption.split("\n")
        at = lines.index("-") if "-" in lines else len(lines)
        lines.insert(at, AI_NOTE)
        caption = "\n".join(lines)

    # 1~2) 인스타가 공개 저장소의 영상 주소를 직접 가져가게 한다
    # (인스타 로그인 방식은 파일 직접 밀어 넣기를 받지 않음 — 2026-10-17 확인)
    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ["GITHUB_SHA"]
    path = urllib.parse.quote(video.as_posix())
    video_url = f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"
    print("영상 주소:", video_url)
    box = call("POST", f"{API}/{USER_ID}/media", params={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true",
        "access_token": TOKEN,
    })
    box_id = box["id"]
    print("상자 만듦:", box_id)

    # 3) 인스타가 영상 처리 끝낼 때까지 기다리기 (최대 10분)
    for _ in range(60):
        st = call("GET", f"{API}/{box_id}", params={"fields": "status_code,status", "access_token": TOKEN})
        print("처리 상태:", st.get("status_code"))
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            sys.exit(f"인스타가 영상 처리 실패: {st}")
        time.sleep(10)
    else:
        sys.exit("10분이 지나도 처리가 안 끝남")

    # 4) 게시
    post = call("POST", f"{API}/{USER_ID}/media_publish", params={"creation_id": box_id, "access_token": TOKEN})
    media_id = post["id"]
    link = call("GET", f"{API}/{media_id}", params={"fields": "permalink", "access_token": TOKEN}).get("permalink", "")
    print("올림:", link)

    # 5) 결과를 다음 단계(기록·폴더 옮기기)에 넘기기
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a", encoding="utf-8") as f:
        f.write(f"link={link}\n")


if __name__ == "__main__":
    main()
