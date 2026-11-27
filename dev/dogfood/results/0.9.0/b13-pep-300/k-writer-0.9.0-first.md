# PEP 659 Specializing Adaptive Interpreter 요약

PEP 659는 바이트코드 명령어를 각각 실행 중에 만난 타입과 값에 맞춘 더 빠른 명령어로 교체하고 타입과 값이 바뀌면 opcode만 바꿔 적은 비용으로 되돌리는 인터프리터를 CPython에 도입하자고 제안합니다. 저자는 광범위한 실험을 근거로 이 인터프리터가 CPython을 최대 50% 빠르게 할 수 있다고 추정했고 그 값은 벤치마크에 따라 크게 달라진다고 밝혔습니다. 이 인터프리터를 도입해도 Python 언어, 라이브러리, API는 바뀌지 않습니다. 이 인터프리터를 구현한 CPython 3.11은 많은 함수가 자주 실행되지 않는 애플리케이션에서 3.10보다 메모리를 더 사용하지만 그 차이는 크지 않습니다.

자료: PEP 659 "Specializing Adaptive Interpreter", Mark Shannon, 2021, pep-0659.rst
