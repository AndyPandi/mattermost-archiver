# Mattermost Archiver

[한국어](README.md) · [English](README.en.md)

**Mattermost 대화와 첨부파일을 브라우저에서 보기 편한 오프라인 HTML 아카이브로 변환합니다.** 팀·채널별 대화와 스레드, 첨부파일 링크를 서버 없이 열람합니다. 결과 HTML은 Windows·macOS·Linux에서 열 수 있습니다.

변환에는 Python 3.9 이상과 표준 라이브러리만 사용합니다(pip 불필요). 아래 명령은 **Mattermost가 Docker Compose로 동작하는 Linux 서버** 기준입니다. HTML 열람에는 Python이나 Mattermost가 필요 없습니다. Windows CLI 실행은 별도 검증하지 않았습니다.

> 원본 export는 DM·비공개 채널 등을 포함하는 서버 전체 민감 데이터입니다. 관리자만 보관하세요. 아래 변환은 공개 채널만 포함하며 DM은 지원하지 않습니다. 완전한 백업·복원 도구가 아닙니다.

먼저 `python3 --version`(3.9+), `command -v git`, `command -v wget`, `command -v curl`로 확인하세요. 새 VM에는 일부 도구가 없을 수 있습니다. [상세 준비 안내](docs/manual.ko.md)를 참고하세요. unzip은 필요 없습니다.

## 1. Mattermost 대화·첨부파일을 ZIP으로 추출

**Mattermost 서버 SSH 터미널에서 실행합니다.** 전체 추출 권한과 여유 공간을 확인하세요. 최종 보관 시에는 메시지·파일 변경을 멈추세요. 예시는 Compose 경로 `/opt/mattermost/compose.yaml`, 서비스 `mattermost`, 로컬 mmctl 활성화를 전제로 합니다.

```sh
sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost /mattermost/bin/mmctl --local export create --include-archived-channels
```

출력된 **Job ID**를 기록합니다. 첨부파일은 기본 포함하며 보관 채널도 포함합니다. 플러그인 데이터 등 모든 서버 객체의 보존을 의미하지는 않습니다.

## 2. 추출 정상 여부 확인

아래 `JOB_ID`를 실제 값으로 바꿉니다.

```sh
sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost /mattermost/bin/mmctl --local export job show JOB_ID
sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost /mattermost/bin/mmctl --local export list
```

**Status가 success이고 목록에 JOB_ID_export.zip이 있을 때만 진행하세요.** pending/in_progress면 같은 작업을 다시 조회하세요. 새 작업을 중복 생성하지 마세요.

다음 `REPLACE_WITH_JOB_ID`를 수정하고 **명령별 성공을 확인하며** 실행합니다. `~/archive-work/raw.zip`이 이미 있으면 새 작업 폴더를 사용해 원본 덮어쓰기를 피하세요.

```sh
umask 077
mkdir -p ~/archive-work
chmod 700 ~/archive-work
JOB_ID="REPLACE_WITH_JOB_ID"
REMOTE_DIR="/tmp/mm-archiver-manual-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
SEED_PARENT="$(mktemp -d)"
mkdir -m 700 "$SEED_PARENT/private"
# Pinned deployment Compose user only; NOT a generic Mattermost UID/GID.
sudo chown 2000:2000 "$SEED_PARENT/private"
sudo docker compose -f /opt/mattermost/compose.yaml cp -a \
  "$SEED_PARENT/private" "mattermost:$REMOTE_DIR"
sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost /mattermost/bin/mmctl --local export download "${JOB_ID}_export.zip" "$REMOTE_DIR/raw.zip"
LOCAL_DIR="$(mktemp -d ~/archive-work/mm-download-XXXXXXXX)"
sudo docker compose -f /opt/mattermost/compose.yaml cp "mattermost:$REMOTE_DIR/raw.zip" "$LOCAL_DIR/raw.zip"
sudo chown "$(id -u):$(id -g)" "$LOCAL_DIR/raw.zip"
chmod 600 "$LOCAL_DIR/raw.zip"
ln "$LOCAL_DIR/raw.zip" ~/archive-work/raw.zip
python3 -m zipfile -t ~/archive-work/raw.zip
```
컨테이너에 mkdir/sh/id/chmod/rm 등이 있다고 가정하지 않습니다. 위 mkdir/chown은 **호스트** 명령이며, 2000:2000은 해당 고정 Compose 배포에서 확인한 사용자에만 적용합니다. 다른 배포는 관리자가 UID:GID를 확인해야 합니다. Docker cp -a는 원본 소유권과 권한을 유지합니다. UUID 경로는 매번 새로 만들고 재사용하지 마세요. 각 명령 실패 시 즉시 중단하세요. ln은 기존 출력을 덮어쓰지 않습니다. 컨테이너의 0700 임시 폴더는 민감한 ZIP을 보호하며 자동 삭제하지 않습니다. 경로를 기록해 보존 정책에 따라 처리하고 서버 원본 export는 삭제하지 마세요. 호스트 임시 폴더도 보존 정책 대상입니다. 컨테이너 /tmp 여유 공간은 관리자가 별도로 확인해야 합니다.


ZIP 검사에서 오류가 없어야 합니다. `umask 077`은 새 파일을 본인만 접근하도록 하는 기본 권한 설정입니다. 위 과정에서 만든 컨테이너 임시 사본은 자동 삭제되지 않습니다.

**기존 export ZIP이 있으면 1~2단계는 생략**하고 아래 입력 경로를 그 파일로 바꾸세요.

## 3. 아카이빙 프로그램 다운로드

**공개 저장소 기준: 서버에서 직접 받습니다.** 업데이트가 쉬운 git clone을 권장하며 로그인·deploy key는 필요 없습니다.

```sh
cd ~
git clone https://github.com/AndyPandi/mattermost-archiver.git
cd mattermost-archiver
python3 --version
```

Git이 없다면 wget 또는 curl로 ZIP을 다운로드할 수 있습니다. 둘 중 하나만 사용하세요.

```sh
cd ~
wget -O mattermost-archiver-main.zip https://github.com/AndyPandi/mattermost-archiver/archive/refs/heads/main.zip

# curl alternative (choose ONE download command)
# curl -fL -o mattermost-archiver-main.zip https://github.com/AndyPandi/mattermost-archiver/archive/refs/heads/main.zip

python3 -m zipfile -e mattermost-archiver-main.zip archiver-source
cd ~/archiver-source/mattermost-archiver-main
python3 --version
```

Python 3.9 이상인지 확인하세요. 기존 폴더·파일이 있다면 새 작업 위치를 사용해 덮어쓰기를 피하세요. Git clone으로 받은 경우 로컬 변경을 확인한 뒤 `git pull --ff-only`로 갱신할 수 있습니다. main은 변경될 수 있으니 검증한 커밋을 기록하거나 고정하세요. 다운로드한 코드를 확인한 후 실행하고 `curl | sh` 같은 즉시 실행은 사용하지 않습니다.

**아직 비공개라면 익명 다운로드는 실패합니다.** GitHub 로그인 후 Code → Download ZIP으로 받아 서버에 전송하세요. 토큰·개인키를 URL에 넣지 마세요.

## 4. 아카이빙 실행

**프로그램 폴더에서 실행하며 sudo는 필요 없습니다.** 목록 확인 후 공개 채널 전체를 변환합니다.

```sh
python3 mattermost_archiver.py list ~/archive-work/raw.zip
python3 mattermost_archiver.py convert ~/archive-work/raw.zip --all-public --timezone Asia/Seoul --output ~/archive-work/archive.zip
```

특정 채널만 선택하려면 `--all-public` 대신 `--channel 팀이름/채널이름`을 사용합니다. 성공하면 결과 경로와 처리 개수가 나옵니다. 기존 출력 ZIP은 덮어쓰지 않습니다.

`metadata_records`는 사용자·권한 정의 등을 원문 그대로 싣지 않았다는 뜻입니다. 다른 제외 항목도 확인하세요. 비공개 채널·카테고리는 [상세 매뉴얼](docs/manual.ko.md)을 참고하세요.

## 5. 파일 확인

서버에서 무결성을 확인합니다.

```sh
python3 mattermost_archiver.py verify ~/archive-work/archive.zip
sha256sum ~/archive-work/archive.zip
```

**본인 PC 터미널**에서 키 경로·서버 IP를 바꾸고 다운로드합니다(서버 사용자 opc 예시).

```sh
scp -i "<SSH_PRIVATE_KEY>" opc@<SERVER_IP>:/home/opc/archive-work/archive.zip .
```

전송 후 서버 SHA-256과 비교하세요: Linux `sha256sum archive.zip`, macOS `shasum -a 256 archive.zip`, Windows PowerShell `Get-FileHash archive.zip -Algorithm SHA256`.

결과 ZIP을 새 폴더에 압축 해제하고 **index.html**을 브라우저로 엽니다. 한글·시간순 대화·스레드 펼치기·첨부파일을 확인하세요. 폴더 구조를 유지하면 인터넷·SSH 터널 없이 열람할 수 있습니다.

첨부파일 저장명은 `파일명__해시뒤8자리.확장자`이며 충돌 시 길이를 늘립니다. 무결성 해시는 전체 SHA-256을 유지합니다.

## 상세 안내

- [상세 매뉴얼](docs/manual.ko.md): 자동 추출, 재개·복구, 자원 제한, 카테고리 및 비공개 채널
- [현재 구현 범위](docs/project-state.md)
- ZIP은 암호화되지 않습니다. 공유 범위를 확인하고, 외부 다운로드·열람 검증 전에 서버를 삭제하지 마세요.
- Markdown은 일반 텍스트로 표시하며 플러그인 데이터 복원은 보장하지 않습니다. 첨부파일은 신뢰할 수 있는 것만 여세요.

첨부 HTML/SVG 다운로드는 소독이 아니며 별도로 열면 활성 콘텐츠가 실행될 수 있습니다. SHA-256 검증은 무결성 확인이지 진위·안전성 보장이 아닙니다.

## 라이선스

이 프로젝트의 코드와 문서는 [MIT License](LICENSE)를 따릅니다. 저작권·허가 고지를 유지하면 상업적 사용, 수정 및 재배포가 가능합니다. 무보증으로 제공됩니다.

Mattermost 자체와 타사 구성요소는 각각의 라이선스를 따릅니다. 추출된 대화·첨부파일에 MIT 라이선스가 자동으로 적용되는 것은 아닙니다.

Docker copy reference: https://docs.docker.com/reference/cli/docker/container/cp/ — -a preserves source UID/GID; copying a directory to a nonexistent destination creates that destination. UUID paths must not be reused. No real Docker validation was performed for this revision.
