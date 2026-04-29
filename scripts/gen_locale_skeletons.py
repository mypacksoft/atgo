"""Generate skeleton dictionaries for the 12 locales we don't hand-translate yet.

Strategy: write only the most-visible strings (nav, common buttons, plan
names, status badges, brand) per locale, hand-translated. Everything else
falls back to English via the deepMerge in i18n/request.ts.

Quality goal: nav + buttons + status feel native; long prose text remains
in English until a community contributor improves it.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "apps" / "portal" / "i18n" / "messages"

TRANSLATIONS = {
  # zh-TW: Traditional Chinese
  "zh-TW": {
    "brand": {"tagline": "ZKTeco 雲端考勤"},
    "nav": {
      "overview": "總覽", "devices": "考勤機", "employees": "員工",
      "branches": "分支機構", "departments": "部門", "attendance": "打卡記錄",
      "presence": "在場員工", "dashboard": "儀表板", "timesheet": "考勤表",
      "sync": "設備同步", "requests": "申請", "domains": "網域",
      "billing": "帳單", "apiKeys": "API 金鑰", "odoo": "Odoo",
      "settings": "設定", "signOut": "登出", "signIn": "登入",
      "signUp": "建立工作區", "pricing": "價格"
    },
    "common": {
      "save": "儲存", "cancel": "取消", "delete": "刪除", "edit": "編輯",
      "add": "新增", "remove": "移除", "search": "搜尋",
      "loading": "載入中…", "saving": "儲存中…", "yes": "是", "no": "否",
      "active": "啟用", "online": "線上", "offline": "離線",
      "today": "今天", "month": "月", "year": "年",
      "noData": "無資料。", "actions": "操作", "verify": "驗證"
    },
    "auth": {
      "signInTitle": "登入", "signUpTitle": "建立工作區",
      "createWorkspace": "建立工作區", "newHere": "新使用者?",
      "alreadyHaveAccount": "已有帳戶?"
    },
    "pricing": {"perMonth": "/月", "free": "免費", "upgrade": "升級", "mostPopular": "最受歡迎"},
    "lang": {"switcherLabel": "語言"}
  },
  # Indonesian
  "id": {
    "brand": {"tagline": "Absensi Cloud untuk ZKTeco"},
    "nav": {
      "overview": "Ikhtisar", "devices": "Perangkat", "employees": "Karyawan",
      "branches": "Cabang", "departments": "Departemen", "attendance": "Log absensi",
      "presence": "Sedang bekerja", "dashboard": "Dasbor", "timesheet": "Lembar waktu",
      "sync": "Sinkronisasi", "requests": "Permintaan", "domains": "Domain",
      "billing": "Penagihan", "apiKeys": "Kunci API", "settings": "Pengaturan",
      "signOut": "Keluar", "signIn": "Masuk", "signUp": "Buat workspace", "pricing": "Harga"
    },
    "common": {
      "save": "Simpan", "cancel": "Batal", "delete": "Hapus", "edit": "Ubah",
      "add": "Tambah", "remove": "Hapus", "search": "Cari", "loading": "Memuat…",
      "yes": "Ya", "no": "Tidak", "active": "Aktif", "online": "Online", "offline": "Offline",
      "today": "Hari ini", "month": "Bulan", "year": "Tahun",
      "noData": "Tidak ada data."
    },
    "auth": {"signInTitle": "Masuk", "signUpTitle": "Buat workspace", "newHere": "Baru di sini?"},
    "pricing": {"perMonth": "/bln", "free": "Gratis", "upgrade": "Tingkatkan"},
    "lang": {"switcherLabel": "Bahasa"}
  },
  # Thai
  "th": {
    "brand": {"tagline": "ระบบลงเวลาคลาวด์สำหรับ ZKTeco"},
    "nav": {
      "overview": "ภาพรวม", "devices": "เครื่องสแกน", "employees": "พนักงาน",
      "branches": "สาขา", "departments": "แผนก", "attendance": "บันทึกการลงเวลา",
      "presence": "กำลังทำงาน", "dashboard": "แดชบอร์ด", "timesheet": "ตารางเวลา",
      "sync": "ซิงค์อุปกรณ์", "requests": "คำขอ", "domains": "โดเมน",
      "billing": "การเรียกเก็บเงิน", "apiKeys": "คีย์ API", "settings": "ตั้งค่า",
      "signOut": "ออก", "signIn": "เข้าสู่ระบบ", "signUp": "สร้างเวิร์กสเปซ", "pricing": "ราคา"
    },
    "common": {
      "save": "บันทึก", "cancel": "ยกเลิก", "delete": "ลบ", "edit": "แก้ไข",
      "add": "เพิ่ม", "loading": "กำลังโหลด…", "yes": "ใช่", "no": "ไม่",
      "active": "ใช้งาน", "online": "ออนไลน์", "offline": "ออฟไลน์",
      "today": "วันนี้", "month": "เดือน", "year": "ปี",
      "noData": "ไม่มีข้อมูล"
    },
    "auth": {"signInTitle": "เข้าสู่ระบบ", "signUpTitle": "สร้างเวิร์กสเปซ", "newHere": "ผู้ใช้ใหม่?"},
    "pricing": {"perMonth": "/เดือน", "free": "ฟรี", "upgrade": "อัปเกรด"},
    "lang": {"switcherLabel": "ภาษา"}
  },
  # Malay
  "ms": {
    "brand": {"tagline": "Kehadiran Awan untuk ZKTeco"},
    "nav": {
      "overview": "Gambaran", "devices": "Peranti", "employees": "Pekerja",
      "branches": "Cawangan", "departments": "Jabatan", "attendance": "Log kehadiran",
      "presence": "Sedang bekerja", "dashboard": "Papan pemuka", "timesheet": "Helaian masa",
      "sync": "Penyegerakan", "requests": "Permintaan", "domains": "Domain",
      "billing": "Pengebilan", "apiKeys": "Kunci API", "settings": "Tetapan",
      "signOut": "Log keluar", "signIn": "Log masuk", "signUp": "Cipta workspace", "pricing": "Harga"
    },
    "common": {
      "save": "Simpan", "cancel": "Batal", "delete": "Padam", "edit": "Edit",
      "add": "Tambah", "search": "Cari", "loading": "Memuatkan…",
      "yes": "Ya", "no": "Tidak", "active": "Aktif", "online": "Dalam talian",
      "today": "Hari ini", "month": "Bulan", "year": "Tahun",
      "noData": "Tiada data."
    },
    "auth": {"signInTitle": "Log masuk", "signUpTitle": "Cipta workspace"},
    "pricing": {"perMonth": "/bln", "free": "Percuma", "upgrade": "Naik taraf"},
    "lang": {"switcherLabel": "Bahasa"}
  },
  # Filipino / Tagalog
  "fil": {
    "brand": {"tagline": "Cloud Attendance para sa ZKTeco"},
    "nav": {
      "overview": "Pangkalahatan", "devices": "Mga device", "employees": "Mga empleyado",
      "branches": "Mga sangay", "departments": "Mga departamento", "attendance": "Log ng pagdalo",
      "presence": "Kasalukuyang nagtatrabaho", "dashboard": "Dashboard", "timesheet": "Timesheet",
      "sync": "Pag-sync", "requests": "Mga kahilingan", "domains": "Mga domain",
      "billing": "Pagbabayad", "apiKeys": "API key", "settings": "Mga setting",
      "signOut": "Mag-logout", "signIn": "Mag-login", "signUp": "Gumawa ng workspace", "pricing": "Presyo"
    },
    "common": {
      "save": "I-save", "cancel": "Kanselahin", "delete": "Tanggalin", "edit": "I-edit",
      "add": "Idagdag", "loading": "Naglo-load…",
      "yes": "Oo", "no": "Hindi", "active": "Aktibo", "online": "Online",
      "today": "Ngayon", "month": "Buwan", "year": "Taon", "noData": "Walang data."
    },
    "auth": {"signInTitle": "Mag-login", "signUpTitle": "Gumawa ng workspace"},
    "pricing": {"perMonth": "/buwan", "free": "Libre", "upgrade": "I-upgrade"},
    "lang": {"switcherLabel": "Wika"}
  },
  # Hindi
  "hi": {
    "brand": {"tagline": "ZKTeco के लिए क्लाउड उपस्थिति"},
    "nav": {
      "overview": "अवलोकन", "devices": "उपकरण", "employees": "कर्मचारी",
      "branches": "शाखाएँ", "departments": "विभाग", "attendance": "उपस्थिति लॉग",
      "presence": "अभी कार्यरत", "dashboard": "डैशबोर्ड", "timesheet": "टाइमशीट",
      "sync": "डिवाइस सिंक", "requests": "अनुरोध", "domains": "डोमेन",
      "billing": "बिलिंग", "apiKeys": "API कुंजी", "settings": "सेटिंग्स",
      "signOut": "साइन आउट", "signIn": "साइन इन", "signUp": "वर्कस्पेस बनाएं", "pricing": "मूल्य"
    },
    "common": {
      "save": "सहेजें", "cancel": "रद्द करें", "delete": "हटाएँ", "edit": "संपादित",
      "add": "जोड़ें", "loading": "लोड हो रहा…",
      "yes": "हाँ", "no": "नहीं", "active": "सक्रिय", "online": "ऑनलाइन",
      "today": "आज", "month": "महीना", "year": "वर्ष", "noData": "कोई डेटा नहीं।"
    },
    "auth": {"signInTitle": "साइन इन", "signUpTitle": "वर्कस्पेस बनाएं"},
    "pricing": {"perMonth": "/माह", "free": "मुफ्त", "upgrade": "अपग्रेड"},
    "lang": {"switcherLabel": "भाषा"}
  },
  # Arabic (RTL)
  "ar": {
    "brand": {"tagline": "حضور سحابي لأجهزة ZKTeco"},
    "nav": {
      "overview": "نظرة عامة", "devices": "الأجهزة", "employees": "الموظفون",
      "branches": "الفروع", "departments": "الأقسام", "attendance": "سجل الحضور",
      "presence": "في العمل حالياً", "dashboard": "لوحة التحكم", "timesheet": "كشف الوقت",
      "sync": "مزامنة الأجهزة", "requests": "الطلبات", "domains": "النطاقات",
      "billing": "الفواتير", "apiKeys": "مفاتيح API", "settings": "الإعدادات",
      "signOut": "تسجيل الخروج", "signIn": "تسجيل الدخول",
      "signUp": "إنشاء مساحة عمل", "pricing": "الأسعار"
    },
    "common": {
      "save": "حفظ", "cancel": "إلغاء", "delete": "حذف", "edit": "تعديل",
      "add": "إضافة", "loading": "جاري التحميل…",
      "yes": "نعم", "no": "لا", "active": "نشط", "online": "متصل", "offline": "غير متصل",
      "today": "اليوم", "month": "الشهر", "year": "السنة", "noData": "لا توجد بيانات."
    },
    "auth": {"signInTitle": "تسجيل الدخول", "signUpTitle": "إنشاء مساحة عمل"},
    "pricing": {"perMonth": "/شهر", "free": "مجاناً", "upgrade": "ترقية"},
    "lang": {"switcherLabel": "اللغة"}
  },
  # Spanish
  "es": {
    "brand": {"tagline": "Asistencia en la nube para ZKTeco"},
    "nav": {
      "overview": "Resumen", "devices": "Dispositivos", "employees": "Empleados",
      "branches": "Sucursales", "departments": "Departamentos", "attendance": "Registro de asistencia",
      "presence": "Trabajando ahora", "dashboard": "Panel", "timesheet": "Hoja de horas",
      "sync": "Sincronización", "requests": "Solicitudes", "domains": "Dominios",
      "billing": "Facturación", "apiKeys": "Claves API", "settings": "Ajustes",
      "signOut": "Cerrar sesión", "signIn": "Iniciar sesión",
      "signUp": "Crear espacio de trabajo", "pricing": "Precios"
    },
    "common": {
      "save": "Guardar", "cancel": "Cancelar", "delete": "Eliminar", "edit": "Editar",
      "add": "Agregar", "loading": "Cargando…",
      "yes": "Sí", "no": "No", "active": "Activo", "online": "En línea", "offline": "Desconectado",
      "today": "Hoy", "month": "Mes", "year": "Año", "noData": "Sin datos."
    },
    "auth": {"signInTitle": "Iniciar sesión", "signUpTitle": "Crear espacio de trabajo"},
    "pricing": {"perMonth": "/mes", "free": "Gratis", "upgrade": "Mejorar"},
    "lang": {"switcherLabel": "Idioma"}
  },
  # Portuguese (Brazil)
  "pt-BR": {
    "brand": {"tagline": "Ponto em nuvem para ZKTeco"},
    "nav": {
      "overview": "Visão geral", "devices": "Dispositivos", "employees": "Funcionários",
      "branches": "Filiais", "departments": "Departamentos", "attendance": "Registro de ponto",
      "presence": "Trabalhando agora", "dashboard": "Painel", "timesheet": "Folha de ponto",
      "sync": "Sincronização", "requests": "Solicitações", "domains": "Domínios",
      "billing": "Faturamento", "apiKeys": "Chaves de API", "settings": "Configurações",
      "signOut": "Sair", "signIn": "Entrar", "signUp": "Criar workspace", "pricing": "Preços"
    },
    "common": {
      "save": "Salvar", "cancel": "Cancelar", "delete": "Excluir", "edit": "Editar",
      "add": "Adicionar", "loading": "Carregando…",
      "yes": "Sim", "no": "Não", "active": "Ativo", "online": "On-line", "offline": "Off-line",
      "today": "Hoje", "month": "Mês", "year": "Ano", "noData": "Sem dados."
    },
    "auth": {"signInTitle": "Entrar", "signUpTitle": "Criar workspace"},
    "pricing": {"perMonth": "/mês", "free": "Grátis", "upgrade": "Atualizar"},
    "lang": {"switcherLabel": "Idioma"}
  },
  # Russian
  "ru": {
    "brand": {"tagline": "Облачный учёт времени для ZKTeco"},
    "nav": {
      "overview": "Обзор", "devices": "Устройства", "employees": "Сотрудники",
      "branches": "Филиалы", "departments": "Отделы", "attendance": "Журнал входа",
      "presence": "Сейчас на работе", "dashboard": "Панель", "timesheet": "Табель",
      "sync": "Синхронизация", "requests": "Запросы", "domains": "Домены",
      "billing": "Оплата", "apiKeys": "API-ключи", "settings": "Настройки",
      "signOut": "Выйти", "signIn": "Войти", "signUp": "Создать рабочее пространство",
      "pricing": "Цены"
    },
    "common": {
      "save": "Сохранить", "cancel": "Отмена", "delete": "Удалить", "edit": "Изменить",
      "add": "Добавить", "loading": "Загрузка…",
      "yes": "Да", "no": "Нет", "active": "Активный", "online": "В сети", "offline": "Не в сети",
      "today": "Сегодня", "month": "Месяц", "year": "Год", "noData": "Нет данных."
    },
    "auth": {"signInTitle": "Войти", "signUpTitle": "Создать рабочее пространство"},
    "pricing": {"perMonth": "/мес", "free": "Бесплатно", "upgrade": "Улучшить"},
    "lang": {"switcherLabel": "Язык"}
  },
  # Turkish
  "tr": {
    "brand": {"tagline": "ZKTeco için bulut puantaj"},
    "nav": {
      "overview": "Genel bakış", "devices": "Cihazlar", "employees": "Çalışanlar",
      "branches": "Şubeler", "departments": "Departmanlar", "attendance": "Devam kayıtları",
      "presence": "Şu an çalışıyor", "dashboard": "Panel", "timesheet": "Mesai çizelgesi",
      "sync": "Cihaz senkronu", "requests": "Talepler", "domains": "Alan adları",
      "billing": "Faturalama", "apiKeys": "API anahtarları", "settings": "Ayarlar",
      "signOut": "Çıkış", "signIn": "Giriş", "signUp": "Çalışma alanı oluştur", "pricing": "Fiyatlar"
    },
    "common": {
      "save": "Kaydet", "cancel": "İptal", "delete": "Sil", "edit": "Düzenle",
      "add": "Ekle", "loading": "Yükleniyor…",
      "yes": "Evet", "no": "Hayır", "active": "Aktif", "online": "Çevrimiçi",
      "today": "Bugün", "month": "Ay", "year": "Yıl", "noData": "Veri yok."
    },
    "auth": {"signInTitle": "Giriş yap", "signUpTitle": "Çalışma alanı oluştur"},
    "pricing": {"perMonth": "/ay", "free": "Ücretsiz", "upgrade": "Yükselt"},
    "lang": {"switcherLabel": "Dil"}
  },
  # French
  "fr": {
    "brand": {"tagline": "Pointage cloud pour ZKTeco"},
    "nav": {
      "overview": "Aperçu", "devices": "Appareils", "employees": "Employés",
      "branches": "Filiales", "departments": "Départements", "attendance": "Journal de pointage",
      "presence": "Au travail", "dashboard": "Tableau de bord", "timesheet": "Feuille de temps",
      "sync": "Synchronisation", "requests": "Demandes", "domains": "Domaines",
      "billing": "Facturation", "apiKeys": "Clés API", "settings": "Paramètres",
      "signOut": "Déconnexion", "signIn": "Connexion",
      "signUp": "Créer un espace de travail", "pricing": "Tarifs"
    },
    "common": {
      "save": "Enregistrer", "cancel": "Annuler", "delete": "Supprimer", "edit": "Modifier",
      "add": "Ajouter", "loading": "Chargement…",
      "yes": "Oui", "no": "Non", "active": "Actif", "online": "En ligne", "offline": "Hors ligne",
      "today": "Aujourd'hui", "month": "Mois", "year": "Année", "noData": "Aucune donnée."
    },
    "auth": {"signInTitle": "Connexion", "signUpTitle": "Créer un espace de travail"},
    "pricing": {"perMonth": "/mois", "free": "Gratuit", "upgrade": "Mettre à niveau"},
    "lang": {"switcherLabel": "Langue"}
  },
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for locale, data in TRANSLATIONS.items():
        path = OUT / f"{locale}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        print(f"  wrote {path.relative_to(OUT.parent.parent.parent)} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
