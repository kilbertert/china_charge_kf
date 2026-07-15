# Hướng dẫn vận hành Tiếng Việt — <DATASET_OPERATION_GUIDE> (vi)

> Nguồn: Bản dịch tiếng Anh từ tài liệu gốc tiếng Trung, mở rộng cho thị trường Đông Nam Á  
> Công dụng: SPEC-D3 Đường dẫn C hướng dẫn thao tác, nút 5030/5031/5032  
> Truy xuất: multi_retrieval, bộ lọc metadata language=vi

## 35 Chương × 3 Phiên bản

### Backend quản lý PC (16 chương)
- Role Management / Shop Level / Individual operator
- Operator review for entry / Add sites under the operator / Site audit
- Billing Template (Charging Station) / Add product model / equipment
- Placement equipment / Charging coupons / Equipment Failure List
- User Management / Financial Management / Order Management
- Operations Management / Data View

### Phiên bản người dùng (9 chương)
- Sign up / top-up / place an order
- Four wheel charging order / Placeholder fee order
- venue / license plate / Change password / Fault Repair

### Phiên bản quản lý đối tác (10 chương)
- Sign up / Real name authentication / Create venue / my venue
- Create template / Venue association template / Placement equipment
- data sector / order / Venue details / Profit withdrawal

## Cấu trúc trường

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| chapter | string | 35 tiêu đề cấp 1 |
| endpoint | enum | user / butler / pc |
| step | int | số bước |
| step_text_vi | text | văn bản tiếng Việt |
| deep_link | string | đường dẫn |
| notes | text | ghi chú |

## Mẫu

### Role Management (pc) bước 1-3
1. Vào hệ thống → Quản lý vai trò
2. Nhấp nút "Thêm" để thêm vai trò
3. Điền biểu mẫu: chọn loại kết thúc, tên vai trò, loại vai trò, mã vai trò, nhấp "Lưu"

### Fault Repair (user) Báo sự cố
1. Mở ứng dụng, nhấp "Của tôi" → "Báo sự cố"
- deep_link: /charge/pages/malfunction/malfunction
- Nút 5032 PHẢI giữ nguyên liên kết này

### Placeholder fee order (user) Phí giữ chỗ
1. Xem chi tiết phí trên trang đơn hàng phí giữ chỗ
- deep_link: /charge/pages/placeUseFeeList/placeUseFeeList

### Profit withdrawal (butler) Rút tiền lợi nhuận
1. Trang chủ quản lý đối tác → Của tôi → Rút tiền
2. Nhập số tiền → Thẻ ngân hàng → Gửi duyệt
- notes: Thanh toán T+1

## Ràng buộc quan trọng (5032)

⚠️ Chuỗi deep_link phải được giữ nguyên văn, không dịch.

## TODO
- [ ] Dịch đầy đủ 35 chương sang tiếng Việt
- [ ] Tham chiếu chéo với 21 nút FAQ
