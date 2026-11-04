# 예시: PagedAttention 논문 정리

이 폴더의 두 글은 `/techblog`로 PagedAttention 논문을 정리한 결과입니다. `paged-attention.default.md`는 합니다체(Default)로 쓴 글이고, `paged-attention.casual.md`는 해요체(Casual)로 쓴 글입니다.

두 글은 K-Writer의 이전 저장소인 [Skill-Techblog](https://github.com/KANG-YEONWOOK/Skill-Techblog)의 0.9.0 버전 스킬을 한 번 실행해서 만들었습니다. 아래의 버전 번호와 commit 해시는 모두 Skill-Techblog의 것입니다. 독자와 분량은 기본값입니다. 독자는 "LLM 서빙과 GPU 메모리 관리 지식이 충분하지 않거나 없을 수 있는 사람"이고, 분량은 공백 제외 5,000~10,000자입니다. 스킬은 Casual로 요청받아도 합니다체 초안을 먼저 쓰고 점검한 뒤, 6단계에서 독립 subagent 세 개에게 차례로 초안 점검을 맡깁니다.

1. 독자 점검: 글만 읽고 독자가 모를 용어를 찾습니다.
2. 후처리: 반복을 삭제하고 빠진 설명을 추가합니다.
3. 한국어 문장 점검: 문장을 하나씩 읽고 직역과 어색한 문장을 수정합니다.

스킬은 점검을 마친 초안의 문장마다 문장 끝(종결부)만 해요체로 바꿔 Casual 글을 만듭니다. 그래서 두 글은 문장 수, 문장 순서, 수치가 같습니다. 2026-11-04에 어색한 단어와 문장을 사람 글 기준으로 두 글에서 똑같이 직접 수정했습니다("낱말"을 "단어"로, "가운데"를 "중"으로, 메모리를 "잡다"를 "할당하다"로 바꾼 것 등). 글을 다시 생성하지 않았고 수치, 헤딩, 표, 코드는 바꾸지 않았습니다.

| 파일 | 어투 | 본문 글자 수(공백 제외) | 문장 수 | lint 결과 |
|---|---|---|---|---|
| [paged-attention.default.md](paged-attention.default.md) | Default(합니다체) | 11,407 | 207 | Gate 0, FAIL 0, WARN 0 |
| [paged-attention.casual.md](paged-attention.casual.md) | Casual(해요체) | 11,236 | 207 | Gate 0, FAIL 0, WARN 0 |

`tone_check.py paged-attention.default.md paged-attention.casual.md`로 두 글을 비교한 결과, 문장 207쌍 모두 문장 끝만 달라서 FAIL과 WARN이 0개였습니다.

Casual 글의 본문은 기본 분량의 상한(10,000자)보다 1,236자 깁니다. 5단계를 마친 초안은 10,279자였고, 처음 나오는 용어의 설명을 6단계에서 추가해 분량이 늘었습니다. 스킬은 이 사실을 보고에 적었습니다. 이 실행 뒤에 초안을 분량 상한보다 10% 짧게 맞추라는 규칙을 추가했습니다(commit 4261d2f).

## 생성 조건

- 실행한 명령은 `/techblog casual ./input.pdf -o article.md --keep-work --defaults`입니다. headless 실행이라 설정 질문을 하지 않도록 `--defaults`를 붙였습니다.
- 모델은 Claude Opus 5.5(`--model opus --effort xhigh`)이고, Claude Code 버전은 2.1.302입니다.
- 스킬은 Skill-Techblog commit ffef9af 버전입니다. Skill-Techblog 0.9.0 최종 버전에는 이 실행에서 찾은 문제를 수정한 내용 다섯 가지가 더 있습니다. 초안을 분량 상한보다 10% 짧게 맞추는 규칙, WebSearch 허용, 이름의 의미를 쓰는 조건(commit 4261d2f), 헤딩 규칙(commit 50e2fe6), 설명 문장을 추가한 뒤 다음 문장의 지시어를 확인하는 규칙(commit 3d6ffd7)입니다.
- `paged-attention.default.md`는 `--keep-work`로 남긴 Default 초안(`article.draft.md`)이고 6단계를 마친 글입니다. `paged-attention.casual.md`는 같은 실행의 출력 파일(`article.md`)입니다.
- 실행에 60.2분이 걸렸고 그중 6단계가 33.6분(56%)이었습니다. 비용은 $19.85였습니다.
- 두 글은 dogfooding iteration 15(iter-090)의 S1 케이스를 실행한 결과입니다. 평가 기록은 [dev/dogfood/REPORT.md](../dev/dogfood/REPORT.md)와 [EVALUATION.md](../EVALUATION.md)에 있습니다.

## 평가 결과

아래 결과는 2026-11-04에 수정하기 전의 글을 평가한 값입니다. 비교 대상은 Skill-Techblog 0.4.0 때 이 폴더에 있던 예시 글(같은 논문, Casual)입니다. judge는 Claude Sonnet입니다.

| 항목 | Skill-Techblog 0.4.0 예시 글 | Skill-Techblog 0.9.0 글 |
|---|---|---|
| 설명이 빠진 용어(terms judge 2회, 1,000자당) | 8.63, 6.31 | 0.27, 0 |
| 어색한 문장(문장 단위 J5, 1,000자당) | 1.11 (168문장 중 10, 그중 8문장은 "잰", "~것으로 봐요" 같은 유형 R) | 0.36 (229문장 중 4) |
| '사용' 의미의 쓰다, 재다 같은 동사(lint A5.native_verbs) | 22개 | 2개 |
| 판단을 옮기는 "~라고 봐요"(lint A7.see_judgment) | 4개 | 0개 |
| 앞 문장을 읽어야 이해되는 문장(J9) | 101문장 중 28 | 129문장 중 25 |

- pairwise judge는 0.4.0 예시 글과 0.9.0 글의 순서를 바꿔 두 번 읽었고, 두 번 모두 0.9.0 글을 선택했습니다. 근거로는 "처음 나오는 말을 거의 빠짐없이 풀어 준다"("토큰은 모델이 텍스트를 나눠 처리하는 단위로 단어나 단어 조각 하나에 해당해요")는 점과, Skill-Techblog 0.4.0 글에 설명 없이 사용한 "memory-bound 작업", "coalesced access" 같은 표현을 들었습니다.
- 독자 점검 subagent는 글에서 독자가 모를 수 있는 용어 99개를 적었고, 그중 28개는 글만 읽어서는 무엇인지, 무엇을 하는지 같은 질문에 답할 수 없는 용어였습니다. 후처리 subagent는 28개를 모두 수정했다고 보고했습니다.
- fidelity judge는 글의 주장 82개를 논문과 대조했고, 근거가 없거나 논문과 다른 주장은 찾지 못했습니다. 용어를 설명하려고 사용한 일반 지식 4개(buddy allocator, copy-on-write, beam이라는 이름, WMT16)도 사실과 맞는다고 판정했습니다.
- style judge는 두 번 채점해서 J2(구체성), J3(deletion test), J4(구조), J6(어투)에 2점, J5(한국어 자연스러움)와 J8(과교정 없음)에 1점을 줬습니다.

## 자료와 라이선스

- 자료: Woosuk Kwon, Zhuohan Li, Siyuan Zhuang, Ying Sheng, Lianmin Zheng, Cody Hao Yu, Joseph E. Gonzalez, Hao Zhang, Ion Stoica, "Efficient Memory Management for Large Language Model Serving with PagedAttention", SOSP 2023. arXiv:2309.06180, https://arxiv.org/abs/2309.06180
- 자료의 라이선스: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- 두 글은 이 논문을 한국어로 요약하고 표, 수식, 예시를 옮긴 2차 저작물입니다. 원문의 구성을 바꿨고, 처음 나오는 용어의 설명과 글쓴이의 해석(표의 수치 비교, 한국어 서비스에 적용할 때의 조건)을 추가했습니다.
