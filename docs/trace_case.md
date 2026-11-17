# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-013 --seed 11
python -m lab9.trace_case --shape fixed --claim C-013 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case của nhóm: kết quả đúng nhưng quyết định sai

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-013@11` (item E-013), run ID `E-seeded_regression-20261117-b989` trong `reports/eval_seeded_regression.json` |
| Triệu chứng | Grader Lab 8 fail với lý do `proposal_mismatch`. Mọi thứ ở mức kết quả đều khớp nhãn: ledger 0đ, `refund_count` 0, status `denied`, reply "đơn O-505 chưa đủ điều kiện hoàn" không nêu số tiền nào. Trước khi có `proposal_correct`, không grader nào của nhóm giải thích được 5 dòng fail của item này (detection 75%). |
| Bước sai đầu tiên | Event 5, kind `proposal`, payload `{"amount_vnd": 0}` |
| Vì sao là bước *đầu tiên* | Event 1 `handoff` đúng contract. Event 2 `investigator` đọc đúng đơn O-505 (trễ 4 ngày, phí ship 35.000). Event 3 `quote` ra 35.000, bằng `proposal_amount` của nhãn. Event 4 `refund_history` đọc đúng 35.000 đã hoàn từ claim trước; đọc lịch sử là việc được phép. Sai bắt đầu ở event 5: agent tự lấy 35.000 − 35.000 = 0 rồi tự kết luận `denied`, thay vì chuyển quote đầy đủ cho host. |
| Failure mode | FM-05 (`pre_deducted`) trong `docs/failure_taxonomy.md` |
| Đối chứng | `fixed C-013@11` không có event `refund_history` hay `proposal`. Quote 35.000 đi thẳng tới host; host từ chối vì `order_already_refunded` và ghi audit `policy_denied`. Ledger snapshot của `fixed` có `policy_denied=True`, của variant lỗi là `False`. |
| Regression test | `src/tests/test_lab9_trace_case.py`, hai test: `test_self_deduction_is_caught_at_the_proposal_not_the_ledger` và `test_fixed_shape_lets_the_host_deny`. Grader bắt được là `ProposalCorrect` (metric `proposal_correct`), thêm vào sau case này. Đã thấy fail trên `seeded_regression` và pass trên `fixed`; `python -m lab9.mutation --detect` tăng từ 75% lên 100%, báo nhầm vẫn 0%. |
| Chưa chắc chắn | Trace không có event nào cho lời gọi `issue_refund`, nên "host không được hỏi" được suy ra từ việc thiếu audit `policy_denied` trong ledger chứ không đọc trực tiếp từ trace. Trace cũng không cho biết vì sao agent tự trừ; MockLLM không sinh lý do. |

Trên C-013 khách không mất tiền: host đằng nào cũng từ chối. Thiệt hại thật của cùng lỗi này nằm ở C-014@11, nơi agent đề xuất 120.000 thay vì 150.000 và host trừ thêm lần nữa, khách chỉ nhận 90.000 thay vì 120.000. C-013 được chọn làm case vì nó là trial mà chỉ đọc ledger và reply sẽ kết luận "đúng".

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
