# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

FAIL là lớp dương: việc của judge là tìm ra câu trả lời hỏng.

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt cả ba | **dùng**, chỉ để theo dõi, không chặn release |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không: κ và recall dưới sàn | **loại** |

Ma trận nhầm lẫn (tp / fp / fn / tn): tone_ok 24 / 4 / 6 / 66; helpful 9 / 0 / 21 / 70.

Tỉ lệ fail quan sát và sau hiệu chỉnh Rogan-Gladen: tone_ok 0.28 → 0.30; helpful 0.09 → 0.30. Judge helpful báo 9% câu trả lời hỏng trong khi người chấm thấy 30%.

## Case audit thủ công

Cột "Ghi chú" lấy từ cột `note` và `human_failure` của CSV; cột "Ai đúng?" là nhận định của nhóm sau khi đọc câu trả lời.

### tone_ok: cả 10 bất đồng

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú và sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha…" | PASS | FAIL | Người | Xưng "em", kết "nha" quá suồng sã. Rubric thêm: xưng "LogiX", gọi khách "anh/chị", không dùng "nha/nhé". |
| 2 | H-017 "Dạ, bạn ơi LogiX đã hoàn 25.000đ…" | PASS | FAIL | Người | Gọi khách là "bạn". Cùng luật xưng hô ở dòng 1. |
| 3 | H-029 "Dạ, vui lòng chờ… không cần nhắn thêm." | PASS | FAIL | Người | Giọng ra lệnh; judge chỉ thấy "Dạ, vui lòng". Rubric thêm: chấm cả câu, từ lịch sự mở đầu không đủ để PASS. |
| 4 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Ngắn nhưng đủ ý; judge phạt vì thiếu lời xin lỗi. Rubric thêm: lời xin lỗi không bắt buộc. |
| 5 | H-051 "Dạ, LogiX đã refund 90.000đ…" | FAIL | PASS | Người | CS LogiX cho phép từ "refund". Rubric thêm danh sách từ mượn được dùng. |
| 6 | H-063 "…đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ." | PASS | FAIL | Người | Hứa hoàn thêm ngoài kết quả hệ thống. Đây là lỗi nội dung về tiền, không phải giọng điệu: chuyển khỏi rubric tone sang grader code. |
| 7 | H-070 "…đã hoàn 90.000đ cho đơn O-909 ạ 😂😂" | PASS | FAIL | Người | Emoji cười trong ngữ cảnh khiếu nại. Rubric thêm: không emoji. |
| 8 | H-081 "Dạ, đơn O-107 chưa đủ điều kiện hoàn…" | FAIL | PASS | **Judge** | Nhãn người sai do đọc nhầm ticket. Việc cần làm là sửa nhãn, không sửa rubric. |
| 9 | H-088 "Dạ, dạ, LogiX đã hoàn 40.000đ…" | FAIL | PASS | Người | Lặp "Dạ" do lỗi gõ. Rubric thêm: lỗi gõ không tính là lỗi giọng điệu. |
| 10 | H-094 "Da, LogiX da hoan 40.000đ cho don O-341…" | PASS | FAIL | Người | Mất dấu tiếng Việt. Kiểm bằng code rẻ và chắc hơn judge: thêm một check dấu trước khi gọi judge. |

Người đúng 9/10, judge đúng 1/10. Sáu bất đồng (dòng 1, 2, 3, 6, 7, 10) là judge bỏ sót, cùng một kiểu: judge coi các dấu hiệu lịch sự bề mặt là đủ.

Nếu sửa nhãn H-081 thành FAIL, tone_ok thành 25 / 3 / 6 / 66, κ 0.784, P 0.893, R 0.806. Số này tính bằng `lab9.stats` trên bản sao trong bộ nhớ; CSV công khai không bị sửa vì test tham chiếu đọc đúng file đó.

### helpful: 5 trong 21 bất đồng

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | HL-015 "Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ." | PASS | FAIL | Người | Sai tiền: ledger ghi 40.000đ. |
| 2 | HL-016 "…thành thật xin lỗi… đã hoàn 55.000đ cho đơn O-404…" | PASS | FAIL | Người | Sai tiền: ledger ghi 35.000đ. Câu dài, nhiều lời xin lỗi, số vẫn sai. |
| 3 | HL-043 "…đã hoàn 35.000đ cho đơn O-202…" | PASS | FAIL | Người | Sai tiền: ledger ghi 20.000đ. |
| 4 | HL-087 "Dạ, LogiX đã hoàn 60.000đ cho đơn O-202 ạ." | PASS | FAIL | Người | Sai tiền: ledger ghi 90.000đ. |
| 5 | HL-047 "Ok bạn, đơn O-515 xử lý rồi nhé." | PASS | FAIL | Người | Sai xưng hô và không nói kết quả xử lý là gì. |

Cả 21 bất đồng đều là judge bỏ sót, người đúng cả 21.

## Kết luận

- **helpful bị loại.** Trong 30 câu người chấm FAIL, judge chỉ bắt 9: đúng 9 câu lỗi bề mặt (4 giọng cụt, 3 không hỏi lại mã đơn, 2 lạc đề). Nó bỏ sót cả 18 câu sai tiền và 3 câu sai xưng hô. Precision 1.0 không cứu được: recall 0.3 nghĩa là một gate dựa trên judge này cho qua 70% câu trả lời hỏng.
- **Vì sao judge không thể bắt lỗi sai tiền.** Judge chỉ đọc câu trả lời, không đọc ledger, nên "đã hoàn 55.000đ" với nó luôn hợp lý. Đây chính là FM-08 và phải chấm bằng code. Biểu thức tách số tiền của grader `reply_matches_ledger` tìm ra số tiền lệch so với ledger ở cả 18/18 câu này.
- **Sau khi tách tiền sang code**, phần còn lại của helpful là 82 câu: 9 / 0 / 3 / 70, κ 0.837, P 1.0, R 0.75. Các con số này đạt sàn, nhưng chỉ có 12 câu FAIL và đây vẫn là chính bộ dữ liệu đã dùng để tìm ra vấn đề. Không dùng lại helpful cho tới khi có nhãn người mới.
- **tone_ok được dùng để theo dõi**, không đưa vào gate: một tiêu chí về giọng điệu không nên chặn release ngang hàng với sai tiền, và 10 bất đồng ở trên cho thấy rubric còn 6 luật phải thêm.
- **Rủi ro còn lại:** judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật. Mỗi lần sửa rubric phải calibrate lại từ đầu, vì các con số ở trên chỉ đúng với rubric cũ.
