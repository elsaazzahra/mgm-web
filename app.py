from flask import  Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import os
from werkzeug.utils import secure_filename
import json
from datetime import datetime

app = Flask(__name__)  # ← INISIALISASI DULU
app.secret_key = 'rahasia123'
app.config['UPLOAD_FOLDER'] = 'static/uploads'  # ← BARU SETTING

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'jpg', 'jpeg', 'png'}

def get_db():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='',  # sesuaikan
        database='mgm_web'
    )

# Route login
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM tb_users WHERE username=%s AND password=%s", (username, password))
        user = cursor.fetchone()
        db.close()

        if user:
            session['username'] = user['username']
            session['role'] = user['role']
            session['id_user'] = user['id_user']
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Username atau password salah!')

    # Saat pertama kali buka halaman (GET), tidak kirim error
    return render_template('login.html')


# Route dashboard – boleh diakses siapa saja
@app.route('/dashboard')
def dashboard():
    username = session.get('username', 'Pengunjung')
    role = session.get('role', 'guest')

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Ambil semua data rumah
    cursor.execute("SELECT * FROM tb_rtlh")
    rumah_list = cursor.fetchall()

    # Statistik total rumah
    total = len(rumah_list)

    # Statistik berdasarkan status
    status_count = {}
    for r in rumah_list:
        status = r['status']
        status_count[status] = status_count.get(status, 0) + 1

    # Ambil daftar desa unik (untuk filter)
    cursor.execute("SELECT DISTINCT desa FROM tb_rtlh ORDER BY desa")
    desa_result = cursor.fetchall()
    desa_list = [d['desa'] for d in desa_result]

    db.close()

    return render_template('dashboard.html',
                           username=username,
                           role=role,
                           rumah_list=rumah_list,
                           total=total,
                           status_count=status_count,
                           desa_list=desa_list,
                           year=datetime.now().year)



def generate_id():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT MAX(id_rtlh) FROM tb_rtlh")
    result = cursor.fetchone()[0]
    db.close()
    if result:
        number = int(result[2:]) + 1
    else:
        number = 1
    return f"RM{number:06d}"


@app.route('/addrumah', methods=['GET', 'POST'])
def add_rumah():
    if request.method == 'POST':
        form = request.form
        files = request.files
        id_rtlh = generate_id()

        def save_file(field):
            file = files.get(field)
            if file and file.filename:
                filename = secure_filename(file.filename)
                path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(path)
                return filename
            return None

        data = (
            id_rtlh,
            form['nama_pemilik'], form['nik'], form['pekerjaan'], form['jumlah_anggota_keluarga'],
            form['alamat'], form['desa'], form['status'], form['sumber_pembiayaan'], form['jumlah_pembiayaan'],
            save_file('foto_rumah_depan'), save_file('foto_rumah_kiri'), save_file('foto_rumah_belakang'),
            save_file('foto_rumah_kanan'), save_file('foto_lantai_rumah'), save_file('foto_rumah_360'),
            form['longitude'], form['latitude'], form['url_google_maps'],
            form['tanggal_mulai'], form['tanggal_selesai']
        )

        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO tb_rtlh (
                id_rtlh, nama_pemilik, nik, pekerjaan, jumlah_anggota_keluarga,
                alamat, desa, status, sumber_pembiayaan, jumlah_pembiayaan,
                foto_rumah_depan, foto_rumah_kiri, foto_rumah_belakang, foto_rumah_kanan,
                foto_lantai_rumah, foto_rumah_360, longitude, latitude, url_google_maps,
                tanggal_mulai, tanggal_selesai
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, data)
        db.commit()
        db.close()
        return redirect(url_for('rumah_list'))

    return render_template('add_rumah.html')


@app.route('/rumah')
def rumah_list():
    q = request.args.get('q')  # ambil kata kunci dari query string
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if q:
        query = """
            SELECT * FROM tb_rtlh
            WHERE nama_pemilik LIKE %s
               OR alamat LIKE %s
               OR desa LIKE %s
        """
        keyword = f"%{q}%"
        cursor.execute(query, (keyword, keyword, keyword))
    else:
        cursor.execute("SELECT * FROM tb_rtlh")

    rumah_list = cursor.fetchall()
    db.close()
    return render_template('rumah_list.html', rumah_list=rumah_list)


@app.route('/editrumah/<id>', methods=['GET', 'POST'])
def edit_rumah(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        form = request.form
        files = request.files

        # Ambil data lama untuk fallback jika tidak upload ulang
        cursor.execute("SELECT * FROM tb_rtlh WHERE id_rtlh = %s", (id,))
        data_lama = cursor.fetchone()

        def update_file(field):
            file = files.get(field)
            if file and file.filename:
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                return filename
            return data_lama.get(field)

        foto_depan = update_file('foto_rumah_depan')
        foto_kiri = update_file('foto_rumah_kiri')
        foto_belakang = update_file('foto_rumah_belakang')
        foto_kanan = update_file('foto_rumah_kanan')
        foto_lantai = update_file('foto_lantai_rumah')
        foto_360 = update_file('foto_rumah_360')

        cursor.execute("""
            UPDATE tb_rtlh SET
                nama_pemilik=%s, nik=%s, pekerjaan=%s, jumlah_anggota_keluarga=%s,
                alamat=%s, desa=%s, status=%s, sumber_pembiayaan=%s, jumlah_pembiayaan=%s,
                foto_rumah_depan=%s, foto_rumah_kiri=%s, foto_rumah_belakang=%s,
                foto_rumah_kanan=%s, foto_lantai_rumah=%s, foto_rumah_360=%s,
                longitude=%s, latitude=%s, url_google_maps=%s,
                tanggal_mulai=%s, tanggal_selesai=%s
            WHERE id_rtlh=%s
        """, (
            form['nama_pemilik'], form['nik'], form['pekerjaan'], form['jumlah_anggota_keluarga'],
            form['alamat'], form['desa'], form['status'], form['sumber_pembiayaan'], form['jumlah_pembiayaan'],
            foto_depan, foto_kiri, foto_belakang, foto_kanan, foto_lantai, foto_360,
            form['longitude'], form['latitude'], form['url_google_maps'],
            form['tanggal_mulai'], form['tanggal_selesai'], id
        ))
        db.commit()
        db.close()
        return redirect(url_for('rumah_list'))

    # GET: tampilkan form dengan data lama
    cursor.execute("SELECT * FROM tb_rtlh WHERE id_rtlh = %s", (id,))
    rumah = cursor.fetchone()
    db.close()
    return render_template('edit_rumah.html', rumah=rumah)


@app.route('/deleterumah/<id>')
def delete_rumah(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM tb_rtlh WHERE id_rtlh=%s", (id,))
    db.commit()
    db.close()
    return redirect(url_for('rumah_list'))

@app.route('/detail/<id>')
def detail_rumah(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM tb_rtlh WHERE id_rtlh = %s", (id,))
    rumah = cursor.fetchone()
    db.close()

    if not rumah:
        return "Rumah tidak ditemukan", 404

    return render_template("detail_rumah.html", rumah=rumah)




#Kelola Admin
def generate_admin_id():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT MAX(id_user) FROM tb_users")
    last = cursor.fetchone()[0]
    db.close()
    if last:
        num = int(last[2:]) + 1
    else:
        num = 1
    return f"AD{num:04d}"


# Tambah admin
@app.route('/add_admin', methods=['GET', 'POST'])
def add_admin():
    if request.method == 'POST':
        nama = request.form['nama']
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        db = get_db()
        cursor = db.cursor()

        # Validasi username unik
        cursor.execute("SELECT * FROM tb_users WHERE username = %s", (username,))
        if cursor.fetchone():
            db.close()
            error = "Username sudah digunakan."
            return render_template("add_admin.html", error=error)

        id_user = generate_admin_id()
        cursor.execute("INSERT INTO tb_users (id_user, nama, username, password, role) VALUES (%s, %s, %s, %s, %s)",
                       (id_user, nama, username, password, role))
        db.commit()
        db.close()
        return redirect(url_for('kelola_admin'))

    return render_template('add_admin.html')


@app.route('/kelola_admin')
def kelola_admin():
    q = request.args.get('q')
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if q:
        cursor.execute("SELECT * FROM tb_users WHERE username LIKE %s ORDER BY id_user", (f"%{q}%",))
    else:
        cursor.execute("SELECT * FROM tb_users ORDER BY id_user")

    admins = cursor.fetchall()
    db.close()
    return render_template('kelola_admin.html', admins=admins)



@app.route('/delete_admin/<id>')
def delete_admin(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM tb_users WHERE id_user = %s", (id,))
    db.commit()
    db.close()
    return redirect(url_for('kelola_admin'))



@app.route('/edit_admin/<id>', methods=['GET', 'POST'])
def edit_admin(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM tb_users WHERE id_user = %s", (id,))
    admin = cursor.fetchone()

    if not admin:
        return "Admin tidak ditemukan", 404

    if request.method == 'POST':
        nama = request.form['nama']
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        # Validasi username unik (kecuali miliknya sendiri)
        cursor.execute("SELECT * FROM tb_users WHERE username = %s AND id_user != %s", (username, id))
        if cursor.fetchone():
            db.close()
            error = "Username sudah digunakan admin lain."
            return render_template("edit_admin.html", admin=admin, error=error)

        cursor.execute("""
            UPDATE tb_users SET nama=%s, username=%s, password=%s, role=%s
            WHERE id_user=%s
        """, (nama, username, password, role, id))
        db.commit()
        db.close()
        return redirect(url_for('kelola_admin'))

    db.close()
    return render_template('edit_admin.html', admin=admin)

@app.route('/admin/<id_user>')
def detail_admin(id_user):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM tb_users WHERE id_user = %s", (id_user,))
    admin = cursor.fetchone()
    db.close()

    if not admin:
        return "Admin tidak ditemukan", 404

    return render_template("detail_admin.html", admin=admin)



# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
