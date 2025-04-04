# กินอะไรที่ไหนดี - Restaurant Finder

เว็บแอปพลิเคชันสำหรับค้นหาร้านอาหารใกล้เคียงตามตำแหน่งปัจจุบันของผู้ใช้

## คุณสมบัติ
- แสดงตำแหน่งปัจจุบันของผู้ใช้บนแผนที่
- ค้นหาร้านอาหารใกล้เคียงอัตโนมัติ
- แสดงรายละเอียดร้านอาหาร เช่น คะแนน จำนวนรีวิว และที่อยู่
- รองรับการแสดงผลบนทุกขนาดหน้าจอ (Responsive Design)

## การติดตั้ง

1. ติดตั้ง Python 3.8 ขึ้นไป
2. Clone repository:
```bash
git clone https://github.com/yourusername/restaurant-finder.git
cd restaurant-finder
```

3. ติดตั้ง dependencies:
```bash
pip install -r requirements.txt
```

4. สร้างไฟล์ .env และกำหนดค่า:
```
GOOGLE_MAPS_API_KEY = your_api_key_here
```

5. รันแอปพลิเคชัน:
```bash
python app.py
```

## การใช้งาน
1. เปิดเว็บบราวเซอร์และไปที่ `http://localhost:5000`
2. อนุญาตการเข้าถึงตำแหน่งเมื่อมีการร้องขอ
3. รอสักครู่เพื่อให้ระบบค้นหาร้านอาหารใกล้เคียง

## การ Deploy
สามารถ deploy บน platform ต่างๆ ได้ดังนี้:

### Heroku
1. ติดตั้ง Heroku CLI
2. Login เข้า Heroku:
```bash
heroku login
```
3. สร้าง app ใหม่:
```bash
heroku create your-app-name
```
4. Push code:
```bash
git push heroku main
```
5. ตั้งค่า environment variables:
```bash
heroku config:set GOOGLE_MAPS_API_KEY=your_api_key_here
```

## License
MIT License 