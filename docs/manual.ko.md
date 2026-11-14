# Mattermost Archiver

[한국어](../README.md) · [English](../README.en.md)

운영 중인 Mattermost에서 데이터를 추출한 뒤 필요한 대화를 선택하여, 오프라인으로 열람하는 아카이브를 만듭니다. **Python 3.9 이상과 표준 라이브러리**만 사용하며 pip 설치는 필요 없습니다. 열람용 도구이며 **Mattermost 백업·복원 도구가 아닙니다**.

## 보안 및 지원 범위

- 반드시 **서버 전체 내보내기 권한**을 확인하세요. 최종적으로 공개 채널 하나만 선택해도 원본 내보내기에는 비공개 채널, 개인·그룹 DM, 사용자 정보, 첨부파일 등 민감한 데이터가 포함될 수 있습니다. 선택 필터는 서버 추출 후 변환 단계에 적용됩니다.
- 변환된 아카이브는 개인·그룹 DM을 지원하지 않습니다. 해당 데이터는 건너뛰고 보고합니다. 비공개 채널은 명시적 포함 설정이 필요합니다. 변환 보고서에서 누락을 확인하세요.
- 원본 ZIP, 상태 파일, 결과 ZIP, 압축 해제 폴더와 전송 위치를 보호하세요. ZIP 자체는 암호화되지 않습니다. 암호화된 저장소와 신뢰할 수 있는 전송 경로를 사용하세요.
- 사용자 이메일과 역할은 뷰어 메타데이터로 복사하지 않습니다. 그러나 본문·첨부파일에 포함된 개인정보나 비밀까지 지우는 기능은 아닙니다.
- 원본 메시지를 삭제하거나 수정하지 않습니다. 추출 과정에서 서버 내보내기 파일이 만들어지며, 서버에 설정된 보존 주기에 따라 만료될 수 있습니다. 서버 정리 정책을 해제하거나 영구 보존을 보장하지 않습니다.
- 플러그인 데이터·투표의 보존을 보장하지 않습니다. Markdown은 Mattermost처럼 완전하게 렌더링하지 않고 이스케이프된 일반 텍스트로 표시합니다. 모든 서버 객체를 완전하게 재현하는 형식이 아닙니다.
- HTML/SVG 등 신뢰할 수 없는 첨부파일은 인라인 표시하지 않고 다운로드 링크로만 제공합니다. 다운로드한다고 안전해지는 것은 아닙니다. 다른 프로그램에서 열면 위험할 수 있습니다.

## 1. 공개 다운로드와 준비 사항

Python 3.9 이상과 OS 시간대 DB가 필요합니다. 새 OCI/Oracle Linux VM에는 Git/wget/unzip이 없을 수 있습니다. 먼저 확인하세요(설치 명령은 자동 실행되지 않으며 관리자가 선택하여 실행합니다).

```sh
python3 --version
command -v git; command -v wget; command -v curl
# Optional on Oracle Linux 9 only; use your OS package manager elsewhere:
# sudo dnf install python3 git curl tzdata
```

공개 저장소는 로그인 없이 HTTPS로 복제합니다. 기존 경로를 덮어쓰지 말고 새 디렉터리를 사용하세요.

```sh
cd ~
git clone https://github.com/AndyPandi/mattermost-archiver.git
cd mattermost-archiver
python3 mattermost_archiver.py --help
```

Git이 없다면 wget 또는 curl 중 하나를 선택합니다. unzip 대신 Python 표준 라이브러리를 사용합니다.

```sh
cd ~
wget -O mattermost-archiver-main.zip https://github.com/AndyPandi/mattermost-archiver/archive/refs/heads/main.zip
# Alternative: choose ONE downloader
# curl -fL -o mattermost-archiver-main.zip https://github.com/AndyPandi/mattermost-archiver/archive/refs/heads/main.zip
python3 -m zipfile -e mattermost-archiver-main.zip archiver-source
cd ~/archiver-source/mattermost-archiver-main
```

**비공개 저장소 대안:** 익명 다운로드가 실패하면 GitHub 로그인 후 Code → Download ZIP으로 받고 서버로 전송하거나, 승인된 SSH 키로 복제하세요. URL에 토큰·키를 넣지 마세요. main은 변경될 수 있으므로 검토한 커밋을 기록·고정하고 실행 전 코드를 확인하세요. 다운로드를 셸에 바로 연결하지 마세요.

아래 예시는 Compose 서비스 `mattermost`, 설정 파일 `/opt/mattermost/compose.yaml`, 서버에 포함된 실행 파일 `/mattermost/bin/mmctl`을 가정합니다. 실제 배포에 맞게 바꾸고, 서버와 함께 제공된 mmctl의 도움말로 버전별 문법을 확인하세요.

Python CLI 자체는 root 권한이 필요하지 않습니다. 다만 추출에는 Docker 데몬·컨테이너 접근 권한이 필요합니다. 일반적인 rootful Docker에서 `docker` 그룹 권한은 사실상 **호스트 root에 준하는 권한**입니다. Rootless Docker도 실제 운영 배포에 접근할 수 있어야 합니다. 권한이 없다면 배포 관리자에게 추출을 요청하고, Docker 소켓을 누구나 쓰도록 바꾸지 마세요.

로컬 mmctl을 사용하려면 Mattermost의 `ServiceSettings.EnableLocalMode`가 활성화되어 있고 컨테이너 명령 실행 사용자가 로컬 Unix 소켓에 접근할 수 있어야 합니다. 비활성화 상태라면 권한 있는 관리자가 기존 설정을 확인·병합하고 배포 절차에 따라 필요한 재시작 또는 설정 반영을 수행해야 합니다. 설정 전체를 덮어쓰지 마세요. 로컬 모드에서는 Mattermost 토큰이 필요 없지만, 그 자체가 높은 권한의 접근 경로입니다.

## 2. 보호된 저장 공간 준비

서버 호스트의 저장소 디렉터리에서 다음을 실행합니다.

```sh
umask 077
df -h .
```

예시는 현재 디렉터리에 결과물을 생성합니다. 결과물이 Git에 들어가지 않도록 하거나, 접근이 제한된 별도 작업 디렉터리를 절대 경로로 지정하세요.

서버 생성 내보내기, 컨테이너 다운로드, 호스트 원본 ZIP, 변환 임시 파일, 결과 ZIP, 로컬 PC의 ZIP 및 압축 해제본 공간이 필요합니다. 여러 복사본이 동시에 존재할 수 있습니다. 원본 ZIP 크기의 몇 배라는 계산은 **대략적인 추정일 뿐 보장이 아닙니다**. 압축 크기만으로 해제 후 크기를 정확히 알 수 없습니다. 서버 내보내기 저장소, 컨테이너 저장소, 임시 공간, 호스트 출력 공간과 로컬 PC 공간을 각각 확인하세요. 첨부파일이 대부분을 차지할 수 있습니다.

## 3. 관리자 수동 추출 (새 OCI VM 기본 경로)

**서버 전체 데이터 추출에 대한 명시적 승인을 받은 뒤에만 실행하세요.** 공개 채널만 변환해도 추출 자체는 전체 서버 범위입니다. 각 명령의 성공을 확인하고 실패하면 중단하세요. 일반 사용자 SSH 셸에서 아래 Docker 명령에만 sudo를 사용합니다. 새 OCI VM은 /opt/mattermost가 root 소유 0700이고 compose 파일은 0600이며 opc는 docker 그룹에 속하지 않습니다. 권한 오류를 우회하려고 디렉터리·env·compose 권한을 완화하거나 Docker 소켓/그룹 권한을 변경하지 마세요. 아래 chown은 새 임시 폴더의 다운로드 파일 하나만 일반 사용자에게 넘깁니다. 이후 list/convert/verify는 sudo 없이 실행하세요.

Docker 호스트에서 실행합니다. 설치된 `mmctl --local export --help`로 문법을 확인하세요. `JOB_ID`와 `ID_export.zip`은 실제 응답 값으로 바꿉니다.

```sh
sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost \
  /mattermost/bin/mmctl --local --json export create --include-archived-channels

# 응답의 작업 ID를 기록하고 성공 여부를 확인합니다.
sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost \
  /mattermost/bin/mmctl --local --json export job show JOB_ID

sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost \
  /mattermost/bin/mmctl --local --json export list

# 목록에 표시된 정확한 파일명을 사용합니다.
REMOTE_DIR="/tmp/mm-archiver-manual-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost \
  mkdir -m 700 "$REMOTE_DIR"
sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost \
  /mattermost/bin/mmctl --local export download ID_export.zip "$REMOTE_DIR/export.zip"

umask 077
LOCAL_DIR="$(mktemp -d ./mm-manual-XXXXXXXX)"
sudo docker compose -f /opt/mattermost/compose.yaml cp \
  "mattermost:$REMOTE_DIR/export.zip" "$LOCAL_DIR/raw.zip"
sudo chown "$(id -u):$(id -g)" "$LOCAL_DIR/raw.zip"
chmod 600 "$LOCAL_DIR/raw.zip"
# ln refuses an existing raw.zip; retain temporary files if any command fails.
ln "$LOCAL_DIR/raw.zip" ./raw.zip
python3 -m zipfile -t raw.zip
sha256sum raw.zip
```

작업 성공을 확인한 뒤 다운로드하세요. 실패하면 작업 오류와 서버 로그를 먼저 확인합니다. 컨테이너 재생성 시 임시 다운로드가 사라질 수 있습니다. 임시 복사본은 조직의 보존 절차에 따라 관리하세요. 위 명령은 원본 메시지나 서버 내보내기 파일을 삭제하지 않습니다.

### 고급 선택 사항: 자동 추출과 재개

다음 Python export 흐름은 **이미 실제 Docker 데몬과 보호된 compose/env 파일에 접근하도록 허가된 사용자만** 사용합니다. 새 OCI VM의 일반 opc 사용자에게 해당 권한이 있다고 가정하지 마세요. 기본 경로는 위 관리자 수동 추출입니다. sudo Python을 권장하지 않습니다. root로 실행하면 다운로드한 mattermost_archiver.py뿐 아니라 import되는 export_live.py도 root로 실행됩니다. 불가피한 관리자 운영은 검토·고정한 리비전의 전체 소스와 import 경로를 root 소유의 일반 사용자 쓰기 불가 위치에 두고, 작업 디렉터리·상태·출력 파일도 보호해야 합니다. 일반 사용자가 수정 가능한 checkout에서 root Python을 실행하지 마세요.

설치된 명령의 옵션을 확인한 뒤 실행 계획을 살펴봅니다.

```sh
python3 mattermost_archiver.py export --help
python3 mattermost_archiver.py export \
  --state export-state.json --output raw.zip \
  --acknowledge-full-server-export \
  --compose-file /opt/mattermost/compose.yaml --dry-run
```

실제로 추출할 때는 `--dry-run`을 제거합니다.

```sh
python3 mattermost_archiver.py export \
  --state export-state.json --output raw.zip \
  --acknowledge-full-server-export \
  --compose-file /opt/mattermost/compose.yaml
```

기본 Compose 실행 문맥이 배포를 올바르게 가리킨다면 `--compose-file`는 생략할 수 있습니다. 확인 플래그는 **선택 채널이 아니라 서버 전체를 추출한다는 사실**에 대한 명시적 동의입니다. 진행 상태를 기록하는 `export-state.json`을 보관하세요. 중단된 경우 바로 새 내보내기를 만들지 말고 같은 상태 파일과 출력 경로로 재개하세요.

작업 생성은 성공했지만 응답이나 상태 저장이 유실되었다면 생성 여부가 모호합니다. 기존 작업과 내보내기 목록에서 실제 작업 ID를 복구한 뒤 재개하세요. 무작정 다시 생성하면 대용량 작업이 중복될 수 있습니다.

```sh
python3 mattermost_archiver.py export \
  --state export-state.json --output raw.zip \
  --acknowledge-full-server-export \
  --compose-file /opt/mattermost/compose.yaml --job-id JOB_ID
```

작업 ID와 내보내기 파일명은 다릅니다. 완료된 작업을 mmctl 목록의 해당 파일과 대조하세요. 보존 정책으로 파일이 만료되었다면 재개로 복구할 수 없으므로 권한을 확인하고 새로 추출해야 합니다.

## 4. 목록 확인 및 대화 선택

```sh
python3 mattermost_archiver.py list raw.zip
python3 mattermost_archiver.py convert --help
```

표시 이름을 추측하지 말고 `list`에서 확인한 정확한 팀·채널 식별자를 사용하세요. 원하는 선택 방식을 사용합니다.

```sh
# 팀 선택: --team 반복 가능
python3 mattermost_archiver.py convert raw.zip --output archive.zip \
  --team engineering --team operations --timezone Asia/Seoul

# 채널 선택: --channel 반복 가능
python3 mattermost_archiver.py convert raw.zip --output archive.zip \
  --channel engineering/town-square --channel operations/incidents \
  --timezone Asia/Seoul

# 지원되는 모든 공개 채널
python3 mattermost_archiver.py convert raw.zip --output archive.zip \
  --all-public --timezone Asia/Seoul
```

비공개 채널은 기본적으로 제외합니다. 권한이 있고 실제로 포함하려는 경우에만 명시적인 팀·채널 선택에 `--include-private`를 추가하세요. 비공개 채널 이름을 지정하는 것만으로 포함 동의를 대신할 수 없습니다. `--all-public`이 비공개 채널까지 포함한다고 해석하지 마세요. 어떤 옵션을 써도 개인·그룹 DM은 지원하지 않습니다.

**선택은 교집합이 아니라 합집합(UNION)입니다.** --team, --channel, --all-public을 함께 쓰면 각각의 범위가 추가됩니다. --team engineering --channel engineering/town-square는 한 채널로 좁히지 않습니다. --include-private를 추가하면 명시적으로 선택한 팀의 모든 비공개 채널도 포함될 수 있습니다. --all-public 단독에 --include-private만 더하면 비공개 채널을 추가하지 않습니다.

공개 채널 하나만 선택하려면 다른 선택 플래그를 붙이지 마세요:

```sh
python3 mattermost_archiver.py convert raw.zip --output one-channel.zip --channel engineering/town-square
```

선택 옵션 `--categories mapping.json`으로 카테고리 묶음을 지정할 수 있습니다. 체크아웃한 구현에서 지원하는 매핑 스키마를 사용하세요. 카테고리는 열람 편의 기능이며 Mattermost의 사용자별 사이드바 상태를 복구하는 기능이 아닙니다. 추출·선택에 필수는 아닙니다.

`--timezone Asia/Seoul`은 표시 시간대이며 원본 타임스탬프를 바꾸지 않습니다. 실행 호스트의 시스템 시간대 데이터베이스에 요청한 IANA 시간대가 있어야 합니다. 데이터베이스가 없다면 해결한 뒤 진행하고 다른 시간대로 조용히 대체하지 마세요.

변환 요약·보고서에서 선택 결과, 건너뛴 개인·그룹 DM, 미지원 레코드, 누락 첨부파일과 한도 도달 여부를 확인하세요. 처리에는 자원 사용 한도가 있습니다. 설정 가능한 항목과 기본값은 `convert --help`를 확인하세요. 신뢰하는 입력에 한해 저장 공간·메모리를 확인한 뒤 한도를 조정하세요. 한도가 모든 악성 ZIP에 대한 안전을 보장하지는 않습니다. 불완전한 변환을 완전한 백업으로 취급하지 마세요.

## 5. 검증과 PC 전송 (Windows/macOS/Linux)

서버의 일반 사용자로 검증합니다. SHA-256은 무결성이지 진위·안전성 또는 완전성 보장이 아닙니다. ZIP과 해시를 모두 바꾸면 탐지할 수 없으므로 신뢰할 수 있는 경로로 해시를 기록하세요.

```sh
python3 mattermost_archiver.py verify archive.zip
sha256sum archive.zip
```

PC의 터미널에서 SSH 호스트·경로를 바꿔 실행하세요. 대상 파일이 없는 새 로컬 폴더를 사용하세요.

```sh
scp user@server:/absolute/path/archive.zip ./archive.zip
```

해시 비교: Linux는 `sha256sum archive.zip`, macOS는 `shasum -a 256 archive.zip`, Windows PowerShell은 `Get-FileHash archive.zip -Algorithm SHA256`을 사용하세요. Linux/macOS에서 Python 3.9+와 같은 소스 리비전이 있으면 로컬에서도 verify할 수 있습니다. Windows CLI 실행은 검증하지 않았습니다. 실패하면 다시 전송하고 해시를 수동으로 고치지 마세요.

## 6. 로컬 압축 해제 및 열람

민감한 원본 raw.zip이 아닌 **변환된 archive.zip**을 OS 압축 해제 기능으로 새 폴더에 풀고 index.html을 브라우저에서 여세요. Python이 있으면 unzip 없이 `python3 -m zipfile -e archive.zip archive-view`도 가능합니다. 열람에는 Python이나 Mattermost가 필요하지 않습니다. 폴더 구조를 유지하고 ZIP 내부 미리보기가 아닌 추출된 HTML을 여세요. 인터넷·공개 서버·SSH 터널은 필요 없습니다.

첨부 HTML/SVG는 다운로드 링크로만 제공하지만 **다운로드는 소독이 아닙니다**. 따로 열면 활성 콘텐츠가 실행될 수 있습니다. 무결성 검증 통과는 파일 안전성 보장이 아닙니다. ZIP과 폴더에 접근·보존 정책을 적용하고, 공유 범위와 누락을 검토한 뒤 외부 복사본을 검증하세요. 원본 삭제는 별도 보존 판단입니다.

## 합성 데이터 테스트

운영 서버에 접근하지 않는 로컬 합성 테스트입니다.

```sh
python3 -m unittest discover -s tests -v
```

통과하더라도 모든 Mattermost 버전·플러그인의 호환성을 인증하는 것은 아닙니다. 서버 버전을 변경하면 권한 있는 대표 내보내기로 실제 결과를 점검하세요.

## 공식 참고 문서

- [Mattermost mmctl 문서](https://docs.mattermost.com/manage/mmctl-command-line-tool.html)
- [Mattermost 문서](https://docs.mattermost.com/) — 설치된 버전의 bulk export 및 로컬 모드 설정 문서를 확인하세요.

버전별 동작은 설치된 mmctl 도움말과 실제 배포 설정을 기준으로 확인하세요.

## 자원 제한·복구·검증 근거

- `--compose-file` 기본값은 `/opt/mattermost/compose.yaml`입니다. `--preflight`는 로컬 모드 접근 및 컨테이너 디스크를 읽기 전용으로 점검하며, `--dry-run`은 Docker를 호출하지 않습니다.
- 카테고리 JSON은 평면 객체입니다: `{"engineering/town-square":"회사", "operations/incidents":"운영"}`. 개인 사이드바 설정은 export에 포함되지 않으므로 자동 복원하지 않습니다.
- 공통 제한: `--max-bytes` 21474836480(압축 입력/전체 압축 해제 바이트), `--max-entries` 100000, `--max-ratio` 200, `--max-line-bytes` 16777216, `--max-records` 1000000.
- 변환 제한: `--max-post-bytes` 268435456(선택 게시글 직렬화 크기), `--max-depth` 50, `--min-free-bytes` 1073741824. 출력 디스크에 전체 비압축 입력 크기의 3배 + 여유 공간을 요구합니다. Python 객체 메모리 및 HTML 증가량 때문에 정확한 RSS/최종 용량 보장은 아닙니다. ZIP 중앙 디렉터리는 할당 전 64 MiB 및 항목 수를 제한하지만 임의의 적대적 업로드 처리용으로 사용하지 마세요.
- 추출 제한: `--poll-interval` 5초, `--poll-timeout` 3600초, `--command-timeout` 600초, `--min-free-bytes` 1073741824. 마지막 값은 호스트/컨테이너의 최소 여유 공간이지 export 크기 예측이 아닙니다.
- state/lock 파일을 유지하여 재시도하세요. 생성 결과가 불명확한 state를 지우고 재시도하지 마세요. 게시 직후 중단되었다면 기존 ZIP을 state의 SHA-256과 비교하세요. 기존 출력은 완료된 경우에도 덮어쓰지 않습니다. 강제 종료는 임시 파일을 남길 수 있으며 원본 export를 일괄 정리하지 않습니다. POSIX flock, 동일 파일시스템 하드링크 및 컨테이너 df/mkdir/stat/rm/rmdir가 필요합니다.
- `verify`는 해시, 크기, 파일 집합과 게시글/답글/채널/첨부 수를 확인합니다. manifest 자체는 서명이 아니며 원본의 완전성을 증명하지 않습니다.
- 합성 테스트 통과만으로 Python 3.9 실제 런타임, OL9/macOS, 운영 서버 또는 브라우저 동작이 검증된 것은 아닙니다. 시간대 DB는 OS에 설치되어 있어야 합니다.

공식 v11.7.0 근거: [export 명령](https://github.com/mattermost/mattermost/blob/v11.7.0/server/cmd/mmctl/commands/export.go), [JSON 출력](https://github.com/mattermost/mattermost/blob/v11.7.0/server/cmd/mmctl/printer/printer.go), [worker](https://github.com/mattermost/mattermost/blob/v11.7.0/server/channels/jobs/export_process/worker.go), [첨부 저장](https://github.com/mattermost/mattermost/blob/v11.7.0/server/channels/app/export.go), [data 상수](https://github.com/mattermost/mattermost/blob/v11.7.0/server/public/model/bulk_export.go). 루트는 `import.jsonl`, 첨부 경로 PATH는 정확히 `data/PATH`입니다. 작업 JSON은 소문자 필드이며 보통 단일 객체 배열입니다. type은 `export_process`, 성공 status는 `success`, 파일명은 `JOBID_export.zip`입니다. 알 수 없는 배치는 추측하지 않고 실패합니다.

### 첨부파일 이름
저장 파일명은 `정규화된파일명__해시뒤8자리.확장자` 형태입니다. 해시는 파일 내용이 아닌 원본 ZIP 내부 경로의 SHA-256입니다. 대소문자를 구분하지 않는 파일명 충돌이 발생하면 12·16자리부터 최대 64자리까지 확장하며, 그래도 충돌하면 덮어쓰지 않고 실패합니다. HTML 표시 이름은 원래 이름을 유지하고 무결성 검증 해시는 전체 SHA-256을 사용합니다. 기존 아카이브는 자동 변경되지 않으므로 원본 export를 새 출력 ZIP으로 다시 변환하세요.
