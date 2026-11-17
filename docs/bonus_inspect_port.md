# Bonus: port 3 grader sang Inspect AI và so khớp kết quả

Ba grader về tiền và phê duyệt được viết lại trên Inspect AI, rồi so từng trial với kết quả của pydantic-evals. Hai bên cho cùng verdict trên cả 840 phép so (4 shape × 70 trial × 3 grader).

```bash
cd src
pip install -r requirements-bonus.txt      # inspect-ai, không nằm trong CI
python -m lab9.inspect_port                # exit 0 chỉ khi mọi trial khớp
```

Lệnh ghi `reports/inspect_compare.json`. Không cần API key: shape tự chạy MockLLM của Lab 8, model `mockllm/model` của Inspect không được gọi lần nào.

## Port cái gì, theo cách nào

| Grader | pydantic-evals (`lab9/graders.py`) | Inspect AI (`lab9/inspect_port.py`) |
|---|---|---|
| `approval_bypass` | `Evaluator` đọc `ctx.output` | `@scorer` đọc `state.store` |
| `refund_amount_correct` | `Evaluator` so ledger với nhãn | `@scorer` so ledger với nhãn |
| `reply_matches_ledger` | tách số tiền bằng regex | tách số tiền bằng cách đọc từng từ |

Mỗi item@seed là một `Sample`; shape chạy trong `solver` và đặt trial vào `state.store`; nhãn đi theo `Sample.metadata`.

Các scorer bên Inspect được viết lại từ luật chấm chứ không gọi lại grader cũ. Nếu chỉ bọc grader cũ thì hai bên luôn khớp và phép so không nói lên điều gì. Với `reply_matches_ledger`, hai bên còn dùng hai cách tách số tiền khác nhau.

## Kết quả

Inspect AI 0.3.290, pydantic-evals 2.68.0, eval set v1 (`b9890ddcbe9a`), seeds 11/22/33/44/55. Cột "True" là số trial grader trả về True ở mỗi bên.

| Shape | Grader | Trial | Khớp | True (pydantic-evals) | True (Inspect) |
|---|---|---|---|---|---|
| `swarm` | `approval_bypass` | 70 | 70 | 0 | 0 |
| `swarm` | `refund_amount_correct` | 70 | 70 | 69 | 69 |
| `swarm` | `reply_matches_ledger` | 70 | 70 | 70 | 70 |
| `fixed` | `approval_bypass` | 70 | 70 | 0 | 0 |
| `fixed` | `refund_amount_correct` | 70 | 70 | 70 | 70 |
| `fixed` | `reply_matches_ledger` | 70 | 70 | 70 | 70 |
| `seeded_regression` | `approval_bypass` | 70 | 70 | 0 | 0 |
| `seeded_regression` | `refund_amount_correct` | 70 | 70 | 60 | 60 |
| `seeded_regression` | `reply_matches_ledger` | 70 | 70 | 55 | 55 |
| `sibling_refund` | `approval_bypass` | 70 | 70 | 20 | 20 |
| `sibling_refund` | `refund_amount_correct` | 70 | 70 | 50 | 50 |
| `sibling_refund` | `reply_matches_ledger` | 70 | 70 | 70 | 70 |

Shape `sibling_refund` (một công tắc lỗi, dựng lúc chạy bằng `make_shape`) có mặt vì `approval_bypass` bằng 0 trên cả ba report đã commit: một scorer luôn trả False cũng sẽ khớp với chúng. Trên shape này grader trả True ở 20 trial, và hai bên vẫn khớp.

## Phép so này chứng minh được gì

- Kết quả chấm không phụ thuộc vào harness: cùng luật, hai framework, cùng verdict trên từng trial.
- Script tự kiểm được chính nó. Khi cố ý làm hỏng bộ tách số tiền bên Inspect, nó báo 15 trial lệch ở `seeded_regression` và exit 1. Khi một sample bị lỗi giữa chừng, nó dừng với lỗi chứ không lặng lẽ bỏ sample đó khỏi phép so.

## Giới hạn

- Chỉ so trên eval set v1 và MockLLM.
- Hai bộ tách số tiền khớp nhau trên các câu trả lời mà `variant_agent` sinh ra. Với cách viết khác (ví dụ có dấu cách giữa số và đơn vị, "35.000 đ") bản Inspect sẽ không đọc được số còn bản regex thì có; trường hợp đó sẽ hiện ra như một dòng lệch.
- Gate và CI vẫn chạy trên pydantic-evals. Bản port là phép kiểm chéo, không thay harness chính.
