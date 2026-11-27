# PEP 659 Specializing Adaptive Interpreter 요약

PEP 659는 바이트코드 명령 하나하나를 실행 중에 만난 타입과 값에 맞는 더 빠른 명령으로 교체하는 specializing adaptive interpreter를 CPython에 추가하자고 제안합니다. 이 인터프리터는 충분히 실행된 명령을 교체하고, 그 명령에 예상과 다른 입력이 반복되면 적은 비용으로 교체 전 명령으로 되돌립니다. 저자는 실험 결과로 보아 이 인터프리터로 CPython이 최대 50% 빨라질 것으로 추정합니다. 이 인터프리터를 추가해도 Python 언어, 라이브러리, API는 바뀌지 않습니다. 다만 대부분의 애플리케이션처럼 거의 실행되지 않는 함수가 많으면 이 인터프리터를 구현한 CPython 3.11은 3.10보다 메모리를 조금 더 사용합니다.

자료: PEP 659 "Specializing Adaptive Interpreter", Mark Shannon, 2021, pep-0659.rst
