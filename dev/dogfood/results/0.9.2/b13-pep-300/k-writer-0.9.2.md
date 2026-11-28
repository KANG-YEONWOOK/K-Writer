# PEP 659 Specializing Adaptive Interpreter 요약

PEP 659는 CPython 3.11에서 specializing adaptive interpreter를 사용하자고 제안합니다. 이 인터프리터는 바이트코드 명령을 실행 중에 만난 타입과 값에 맞는 더 빠른 명령으로 바꾸고 이후 다른 타입과 값을 만나는 일이 반복되면 바꾸기 전의 명령으로 되돌립니다. 저자 Mark Shannon은 실험 결과를 근거로 이 인터프리터가 CPython을 최대 50%까지 빠르게 한다고 추정합니다. 이 인터프리터를 사용해도 Python의 언어, 라이브러리, API는 바뀌지 않습니다. 다만 대부분의 애플리케이션에서는 함수 중 많은 수가 비교적 적게 실행되므로 CPython 3.11이 3.10보다 메모리를 조금 더 사용합니다.

자료: PEP 659 "Specializing Adaptive Interpreter", Mark Shannon, 2021, pep-0659.rst
