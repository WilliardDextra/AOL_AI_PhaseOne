# Tes AI sederhana - klasifikasi buah (apel atau jeruk)
# Pastikan kamu sudah install scikit-learn dengan: pip install scikit-learn

from sklearn import tree

# Data latih (fitur): [berat (gram), tekstur (0 = halus, 1 = kasar)]
X = [
    [150, 0],  # apel
    [170, 0],  # apel
    [140, 1],  # jeruk
    [130, 1],  # jeruk
]

# Label (hasil yang benar)
y = ['apel', 'apel', 'jeruk', 'jeruk']

# Membuat model Decision Tree
clf = tree.DecisionTreeClassifier()
clf = clf.fit(X, y)

# Coba prediksi buah baru
buah_baru = [[150, 1]]  # berat 160 gram, tekstur halus
hasil = clf.predict(buah_baru)

print("🍏 AI memprediksi bahwa ini adalah:", hasil[0])
