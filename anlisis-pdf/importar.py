"""
Importa el XLSX generado al presupuesto del proyecto activo y guarda GG/Utilidad/IGV.
Ejecutar desde la raiz del proyecto:
  python manage.py shell -c "exec(open(r'C:/xampp/htdocs/structure/anlisis-pdf/importar.py', encoding='utf-8').read())"
"""
import json
from decimal import Decimal

XLSX         = r'C:\xampp\htdocs\structure\anlisis-pdf\1.00 PRESUPUESTO DE PAVIMENTACION.xlsx'
PORCENTAJES  = r'C:\xampp\htdocs\structure\anlisis-pdf\porcentajes.json'

from apps.proyectos.models import Proyecto
from apps.presupuesto.models import Presupuesto
from apps.presupuesto.importador import importar_presupuesto_excel

pcts    = json.load(open(PORCENTAJES))
gg_pct  = Decimal(pcts['gg'])
ut_pct  = Decimal(pcts['ut'])
igv_pct = Decimal(pcts['igv'])
print(f"GG: {gg_pct}%  |  Utilidad: {ut_pct}%  |  IGV: {igv_pct}%")

proyecto = Proyecto.objects.filter(activo=True).first()
if not proyecto:
    print("ERROR: No hay proyecto activo.")
else:
    presupuesto, created = Presupuesto.objects.get_or_create(proyecto=proyecto)
    print(f"Proyecto: {proyecto.nombre}")

    class FakeFile:
        def __init__(self, path):
            self.name = path
            self._data = open(path, 'rb').read()
        def read(self):
            return self._data

    total = importar_presupuesto_excel(FakeFile(XLSX), presupuesto)

    presupuesto.gastos_generales_pct = gg_pct
    presupuesto.utilidad_pct         = ut_pct
    presupuesto.igv_pct              = igv_pct
    presupuesto.save(update_fields=['gastos_generales_pct', 'utilidad_pct', 'igv_pct'])

    cd  = presupuesto.costo_directo()
    tot = presupuesto.total_presupuesto()
    print(f"\nImportadas {total} partidas.")
    print(f"Costo Directo:     S/ {cd:,.2f}")
    print(f"GG ({gg_pct}%):          S/ {presupuesto.gastos_generales():,.2f}")
    print(f"Utilidad ({ut_pct}%):    S/ {presupuesto.utilidad():,.2f}")
    print(f"Sub Total:         S/ {presupuesto.sub_total():,.2f}")
    print(f"IGV ({igv_pct}%):         S/ {presupuesto.igv():,.2f}")
    print(f"TOTAL PRESUPUESTO: S/ {tot:,.2f}")
    print(f"\nVer en: http://localhost/presupuesto/proyecto/{proyecto.pk}/")
