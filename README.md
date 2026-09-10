# eth-autotrade-bot

이더리움 선물 15분봉 스윙 매매 봇입니다.
전략을 만드는 것보다 **전략을 안전하게 바꾸는 절차**를 만드는 데 시간을 더 썼습니다.

<p>
  <img src="https://img.shields.io/badge/Python_3.10-3776AB?style=flat-square&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white"/>
  <img src="https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white"/>
  <img src="https://img.shields.io/badge/VectorBT-4B8BBE?style=flat-square"/>
  <img src="https://img.shields.io/badge/Upstage_Solar-7C3AED?style=flat-square"/>
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square"/>
</p>

> 실전 소액 투입 직전에 멈춘 프로젝트입니다. 실거래로 검증된 수익률은 없습니다.
> 아래에 어디까지 했고 무엇을 안 했는지 그대로 적어 뒀습니다.

<br/>

## 1. 무엇이 어려웠나

자동매매를 만들어 보면 전략을 짜는 것보다 **바꾸는 게** 어렵습니다.

- 전략 코드를 고치려면 봇을 껐다 켜야 하는데, 그 사이 포지션이 떠 있으면 상태를 잃습니다
- 백테스트가 좋게 나왔다고 바로 실전에 넣으면 거의 항상 다르게 움직입니다
- 수수료와 슬리피지를 빼고 재면 숫자가 통째로 뒤집힙니다

그래서 교체 절차를 먼저 만들었습니다.

<br/>

## 2. 전략을 네 자리로 나눴다

```
strategy.py            지금 돈을 넣고 돌리는 것
strategy_candidate.py  새로 만든 후보
strategy_shadow.py     후보를 돈 없이 같은 시장에 태워 보던 자리. 지금은 안 쓴다
strategy_backup.py     직전 버전. 바꿨다가 나빠지면 되돌아온다
```

백테스트 수치가 좋다고 바로 바꾸지 않습니다.
처음에는 후보를 같은 시장에 실시간으로 같이 태워 보는 섀도 루프를 `main.py` 안에 뒀습니다.
2026-02-23 에 이 루프를 뺐고, 지금은 백테스트 리포트를 보고 텔레그램에서 승인하면 교체합니다.

교체할 때는 `importlib` 으로 전략 모듈만 다시 불러옵니다.
프로세스를 죽이지 않으니 포지션 상태가 유지됩니다.

<br/>

## 3. AI가 하는 일과 안 하는 일

`utils/ai_analyzer.py` 와 `research/evolve.py` 가 Upstage Solar(`solar-pro3`)를 호출합니다. 쓰는 곳은 두 군데입니다.

1. 1시간마다 시장 지표를 요약해서 텔레그램으로 보낸다 (`ai_analyzer.py`)
2. 지금 전략 코드를 주고 고친 후보를 짜게 한다. 문법 오류로 죽으면 그 에러를 다시 넣어서 고치게 한다 (`evolve.py`)

**투입 결정은 AI가 하지 않습니다.**
백테스트 리포트를 텔레그램으로 보내고, 사람이 승인해야 실전에 들어갑니다.
AI가 만든 전략을 AI가 승인하게 두면 잘못됐을 때 어디서부터 잘못됐는지 아무도 모릅니다.

<br/>

## 4. 진입 판단

| 지표 | 쓰는 이유 |
|---|---|
| Volume Profile (VAL / VAH / POC) | 히스토그램으로 매물대가 몰린 구간을 찾는다 |
| CVD (누적 거래량 델타) | 매수와 매도의 실제 균형을 봐서 가짜 돌파를 거른다 |
| ADX + EMA 200 | 추세가 약하거나 장기 추세와 반대면 들어가지 않는다 |

손실 관리는 이렇게 뒀습니다.

- 가격이 POC 에 닿으면 손절을 진입가로 올린다
- ROE 7% 를 넘으면 손절을 +5% 로 올린다
- 청산은 `reduceOnly` 로 넣는다. 이걸 안 하면 청산 주문이 반대 포지션을 새로 만든다

`reduceOnly` 는 테스트 중에 실제로 사고를 내고 나서 넣었습니다.

<br/>

## 5. 구조

```
src/
├── core/
│   ├── main.py          15분봉 엔진. 트레일링 스탑과 자가 진단
│   ├── trader.py        바이낸스 선물 주문 집행, 잔고 조회
│   └── db_manager.py    SQLAlchemy 로 포지션 상태 저장과 복구
├── strategies/
│   ├── strategy.py
│   ├── strategy_candidate.py
│   ├── strategy_shadow.py
│   └── strategy_backup.py
├── research/
│   ├── backtester.py
│   ├── optimize.py
│   └── evolve.py        VectorBT 백테스트와 최적화 루프
└── utils/
    ├── fetcher.py       바이낸스 OHLCV 증분 수집
    ├── indicators.py    VP, CVD, Squeeze Momentum
    ├── ai_analyzer.py   Solar 호출과 에러 자가 진단
    └── admin_bot.py     텔레그램 리포트와 승인
```

<br/>

## 6. 어디까지 했나

**한 것**

- [x] 바이낸스 페이지네이션 수집기
- [x] Volume Profile 과 CVD 지표 구현
- [x] SQLite 기반 포지션 영속성. 재시작해도 포지션을 잃지 않는다
- [x] 전략 진화 엔진과 문법 오류 자가 수선 루프
- [x] 텔레그램 승인 시스템
- [x] Docker 안에서 Plotly 차트 생성 안정화
- [x] 실전 루프 안에서 섀도 전략 같이 돌리기 (2026-02-23 에 뺐다. 지금은 안 쓴다)
- [x] 실제 선물 주문 모듈

**안 한 것**

- [ ] 소액 실전 투입
- [ ] 클라우드 배포와 24시간 가동
- [ ] 수익 곡선 모니터링

실전 직전에서 멈췄습니다. 계속 붙들기보다 여기서 배운 걸 더 큰 프로젝트에 쓰는 게 낫다고 봤습니다.

<br/>

## 7. 여기서 배운 것

제일 크게 남은 건 **백테스트 수치를 그대로 믿으면 안 된다**는 것입니다.

수수료(0.04%)를 넣기 전과 후가 완전히 다른 결과였습니다. 슬리피지는 이 봇의 백테스트에 넣지 못했습니다.
비용을 빼고 재면 이겨 보이는 전략이, 넣고 재면 지는 전략이 됩니다.

그래서 다음 프로젝트에서는 처음부터 거래비용과 생존편향 보정을 넣고 시작했습니다.
섀도로 먼저 돌려 보는 습관도 그대로 가져갔습니다.

<br/>

## 8. 실행

API 키는 저장소에 없습니다. 환경변수로 넣습니다.

```bash
# .env 를 만들고 아래 다섯 개를 채운다 (.env.example 은 저장소에 없다)
# BINANCE_API_KEY, BINANCE_SECRET_KEY, UPSTAGE_API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
```

```bash
docker compose up -d
```

<br/>

## 9. 주의

투자 조언이 아닙니다. 학습용으로 만든 코드이고 실거래 검증을 거치지 않았습니다.
이 코드를 그대로 돌려서 생긴 손실에 대해 책임지지 않습니다.

MIT License
