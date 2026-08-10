# Documentación técnica: Facturación electrónica SUNAT (Perú) + Consulta de RUC/DNI

> Extraído del sistema **FarmaSystem** (POS de farmacia, PHP + PostgreSQL) para servir de
> referencia a la hora de implementar la misma funcionalidad en otro sistema/stack.
> Todo lo referente a **catálogos SUNAT, reglas tributarias y estructura UBL 2.1 es
> independiente del lenguaje** — se puede portar tal cual a Node, Laravel, Django, etc.
> Lo específico de PHP/PostgreSQL está marcado como tal.

---

## 0. Resumen del alcance

Dos funcionalidades relacionadas pero independientes:

1. **Consulta de RUC/DNI** — autocompletar datos de un cliente o de la empresa emisora
   a partir de su número de documento, usando un servicio externo (Factiliza).
2. **Facturación electrónica SUNAT** — emitir Boletas, Facturas y Notas de Crédito
   electrónicas: construir XML UBL 2.1, firmarlo digitalmente (XMLDSig con certificado
   `.pfx`), empaquetarlo en ZIP, enviarlo por SOAP al webservice de SUNAT (`billService`),
   y procesar la respuesta (CDR - Constancia de Recepción).

**Nota importante sobre nomenclatura:** en el código hay una columna `nubefact_response`
y una carpeta `conexion_sunat/` que sugieren integración con la API de terceros
**Nubefact**, pero **no es así**: el flujo real (`enviar_sunat()`) habla directo por SOAP
con SUNAT sin pasar por Nubefact. El nombre de columna es un remanente histórico (el
sistema usó Nubefact antes y luego migró a envío directo, pero no renombraron la
columna). Al portar esto a otro sistema, ignora el nombre "nubefact" y asume solo
integración directa SUNAT.

---

## 1. Consulta de RUC / DNI

### 1.1 Proveedor externo

Servicio usado: **Factiliza** (`api.factiliza.com`), API REST con autenticación Bearer
(JWT).

```
GET https://api.factiliza.com/pe/v1/dni/info/{numero}   (numero = 8 dígitos)
GET https://api.factiliza.com/pe/v1/ruc/info/{numero}    (numero = 11 dígitos)

Headers:
  Authorization: Bearer <token>
  Accept: application/json
```

⚠️ **Seguridad:** el código fuente original tenía el token de Factiliza **hardcodeado
en texto plano** dentro del PHP (mala práctica, no auditoría de secreto). **No copies
ese token** al nuevo sistema — debe leerse desde variable de entorno / vault, y cada
implementación debería usar su propia cuenta/token de Factiliza (o un proveedor
equivalente: existen varias APIs similares en Perú — RENIEC/SUNAT no exponen consulta
pública gratuita directa, por eso se usan agregadores como Factiliza, apis.net.pe,
DecolectaAPI, etc.).

### 1.2 Reglas de negocio

- Si el número tiene **8 dígitos** → se asume DNI → se llama al endpoint `/dni/info/`.
- Si tiene **11 dígitos** (o cualquier longitud ≠ 8) → se asume RUC → `/ruc/info/`.
- Validación previa antes de llamar a la API:
  - DNI: debe matchear `^\d{8}$` exactamente.
  - RUC: debe matchear `^\d{11}$` exactamente.
- Si `http_code >= 400` o `data.status >= 400` en la respuesta → se trata como "no
  encontrado" y se devuelve el mensaje de error del proveedor (o uno genérico).

### 1.3 Mapeo de la respuesta a los campos del formulario

**Para DNI**, de `data.*` del proveedor se toman:

| Campo proveedor | Campo interno |
|---|---|
| `nombres` | `nombres` |
| `apellido_paterno` + `apellido_materno` (concatenados) | `apellidos` |
| `direccion` | `direccion` |
| `ubigeo_sunat` (si viene `"-"` se descarta y queda vacío) | `ubigeo` |

**Para RUC**, de `data.*`:

| Campo proveedor | Campo interno |
|---|---|
| `nombre_o_razon_social` | `nombres` (se usa como razón social completa) |
| — | `apellidos` = `''` (vacío, RUC no tiene apellidos) |
| `direccion` | `direccion` |
| `ubigeo_sunat` (igual regla del `"-"`) | `ubigeo` |

### 1.4 Uso de esos datos

El resultado alimenta tanto:
- El formulario de **alta/edición de cliente** (para boletas/facturas a nombre de
  terceros).
- La **configuración de la empresa emisora** (tenant): razón social, dirección, ubigeo,
  RUC — estos son los datos que luego se usan como emisor en el XML SUNAT (ver §3).

### 1.5 Endpoint interno de referencia (contrato sugerido)

```
POST /clientes/lookup_document
Body: { "tipo_documento_id": 6, "numero_documento": "20123456789" }

200 OK
{
  "error": false,
  "message": "Documento consultado correctamente",
  "cliente": {
    "nombres": "...",       // o razón social si es RUC
    "apellidos": "",
    "direccion": "...",
    "ubigeo": "150101"       // 6 dígitos INEI, o "" si no disponible
  }
}

404 / 422 en caso de error, con { "error": true, "message": "..." }
```

---

## 2. Datos maestros necesarios (modelo de datos)

### 2.1 Empresa emisora (tenant / configuración global)

Un solo registro por empresa que emite comprobantes:

```
ruc                    VARCHAR(11)   -- RUC del emisor
business_name          VARCHAR       -- Razón social
trade_name             VARCHAR       -- Nombre comercial
direccion              TEXT
ubigeo                 VARCHAR(6)    -- código INEI
departamento           VARCHAR
provincia              VARCHAR
distrito               VARCHAR
sunat_username         VARCHAR       -- usuario SOL (SIN el RUC delante)
sunat_password         VARCHAR       -- clave SOL (guardar cifrado/hasheado si es posible)
certificate_path       VARCHAR       -- ruta al .pfx del certificado digital
certificate_password   VARCHAR       -- clave del .pfx
certificate_expires_at DATE          -- para alertar vencimiento
sunat_server           VARCHAR(1)    -- '1' = producción, '3' (default) = beta/sandbox
tax_enabled            BOOLEAN       -- flag para activar/desactivar facturación electrónica
```

El **usuario SOAP real** que se envía a SUNAT es `RUC + sunat_username` concatenados
(ver §4.5).

### 2.2 Cliente (comprador)

```
tipo_documento_codigo  VARCHAR(1)   -- catálogo SUNAT 06: '1'=DNI, '6'=RUC, '0'=Otros, '4'=Carnet ext., '7'=Pasaporte
numero_documento       VARCHAR(15)
razon_social /
nombre_completo        VARCHAR      -- nombre a mostrar en el comprobante
direccion              TEXT
ubigeo                 VARCHAR(6)
```

**Cliente genérico "Varios" (ventas sin identificar comprador):** se usa un cliente
especial con `numero_documento = '00000000'` y nombre que contiene la cadena
`'CLIENTES VARIOS'`. Solo válido para **tickets/notas de venta** (no fiscales) o boletas
de bajo monto — SUNAT exige identificar al comprador en **facturas** (siempre) y en
**boletas > S/ 700** (regla peruana vigente, verificar monto actualizado). Este patrón
se detecta comparando el documento contra `'00000000'` o el nombre contra
`'CLIENTES VARIOS'`.

### 2.3 Producto (línea de venta) — campos tributarios

```
afectacion_igv_codigo  VARCHAR(2)   DEFAULT '10'   -- catálogo SUNAT 07 (ver tabla §2.5)
afectacion_tipo         VARCHAR(5)                  -- 'GRAV' | 'EXO' | 'INA' | 'EXP' (derivado del código si no viene)
porcentaje_igv          DECIMAL(5,2) DEFAULT 18.00  -- se guarda por producto para soportar cambios de tasa a futuro
incluye_igv              BOOLEAN     DEFAULT TRUE    -- true = precio_venta es precio final (IGV incluido)
icbper_activo             BOOLEAN     DEFAULT FALSE   -- true = aplica impuesto a bolsas plásticas
factor_icbper             DECIMAL(10,4) DEFAULT 0     -- monto ICBPER por unidad vendida
unidad_codigo             VARCHAR(3)  DEFAULT 'NIU'   -- catálogo SUNAT 03 (NIU=unidad, ZZ=servicios)
codigo_sunat              VARCHAR(8)  DEFAULT '00000000'  -- código de producto SUNAT (opcional)
product_type              VARCHAR(20) DEFAULT 'product'   -- 'product' | 'service' (servicios ⇒ unidad 'ZZ')
```

### 2.4 Venta / comprobante

```
serie                   VARCHAR(4)
correlativo              VARCHAR(8)
codigo_tipo_documento     VARCHAR(2)   -- '01' factura, '03' boleta, '07' nota crédito, '08' nota débito
moneda_codigo             VARCHAR(3)   DEFAULT 'PEN'
sunat_forma_pago          VARCHAR(20)  DEFAULT 'Contado'  -- 'Contado' | 'Credito'
gravada / exonerada /
inafecta / gratuita       DECIMAL(18,2)   -- totales por tipo de afectación
icbper                    DECIMAL(18,2)
monto_credito             DECIMAL(18,2)   -- solo si forma_pago = Credito
```

Y por cada línea (`venta_detalles`):

```
unidad_codigo, afectacion_igv_codigo, codigo_sunat, codigo_interno
cantidad, valor_unitario (sin IGV, hasta 10 decimales), valor_total (sin IGV, 2 decimales)
igv (monto IGV de la línea), icbper (monto ICBPER de la línea)
precio_unitario (con IGV, para mostrar), precio_total (con IGV + ICBPER)
```

### 2.5 Catálogo — Afectación al IGV (catálogo SUNAT 07)

Usado para decidir cómo tributa cada línea:

| Código | Descripción | Tipo | Uso típico |
|---|---|---|---|
| `10` | Gravado - Operación Onerosa | `GRAV` | Venta normal con IGV 18% |
| `20` | Exonerado - Operación Onerosa | `EXO` | Productos exonerados (ej. medicinas exoneradas, zona selva) |
| `21` | Exonerado - Transferencia Gratuita | `EXO` | |
| `30` | Inafecto - Operación Onerosa | `INA` | |
| `31`–`36` | Inafecto - Retiro (bonificación/muestra/premio/etc.) | `INA` | |
| `40` | Exportación | `EXP` | |

(Existen más códigos gravados 11–17 para retiros/bonificaciones, poco usados en un
POS minorista — incluidos por completitud en la tabla semilla.)

Mapeo código → categoría UBL usado al construir el XML:

| Afectación | `TaxCategory/ID` | `TaxScheme/ID` | `TaxScheme/Name` | `TaxTypeCode` |
|---|---|---|---|---|
| Gravado (`10`) | `S` | `1000` | `IGV` | `VAT` |
| Exonerado (`20`,`21`) | `E` | `9997` | `EXO` | `VAT` |
| Inafecto (`30`–`36`) | `O` | `9998` | `INA` | `FRE` |

### 2.6 Catálogo — Tipo de documento de identidad (catálogo SUNAT 06)

| Código | Descripción |
|---|---|
| `0` | Otro tipo de documento |
| `1` | DNI |
| `4` | Carnet de extranjería |
| `6` | RUC |
| `7` | Pasaporte |
| `A` | Cédula diplomática de identidad |

### 2.7 Catálogo — Motivo de Nota de Crédito (catálogo SUNAT 09)

| Código | Descripción |
|---|---|
| `01` | Anulación de la operación |
| `02` | Anulación por error en el RUC |
| `03` | Corrección por error en la descripción |
| `04` | Descuento global |
| `05` | Descuento por ítem |
| `06` | Devolución total |
| `07` | Devolución por ítem |
| `08` | Bonificación |
| `09` | Disminución en el valor |
| `10` | Otros conceptos |
| `11` | Ajustes de operaciones de exportación |
| `12` | Ajustes afectos al IVAP |

### 2.8 Tabla de series/numeración por tipo de documento

Un correlativo atómico por tipo (evita duplicados con concurrencia):

```
series_comprobantes (
  tipo   PRIMARY KEY,   -- 'boleta' | 'factura' | 'nota_credito' | 'nota_credito_boleta' | 'nota_credito_factura'
  serie                 -- 'B001' | 'F001' | 'NC01' | 'BC01' | 'FC01'
  ultimo_numero
)
```

Convención de series usada:

| Tipo | Serie |
|---|---|
| Boleta | `B001` |
| Factura | `F001` |
| Nota de crédito (genérica) | `NC01` |
| Nota de crédito sobre Boleta | `BC01` |
| Nota de crédito sobre Factura | `FC01` |

La serie de la nota de crédito se elige **según el tipo de documento que se está
anulando/corrigiendo**: si el comprobante original es factura (`codigo_tipo_documento
== '01'`) usa `FC01`; si es boleta (`'03'`) usa `BC01`.

**Incremento atómico** (patrón SQL, evita condición de carrera sin necesitar un
`SELECT ... FOR UPDATE` separado — el `UPDATE ... RETURNING` es atómico a nivel de fila
en PostgreSQL):

```sql
UPDATE series_comprobantes
SET ultimo_numero = COALESCE(ultimo_numero, 0) + 1
WHERE tipo = :tipo AND activo = TRUE
RETURNING serie, ultimo_numero, codigo_tipo_documento;
```

El correlativo final se formatea a 8 dígitos con ceros a la izquierda:
`str_pad(numero, 8, '0', STR_PAD_LEFT)`.

### 2.9 Comprobante electrónico (registro de emisión)

```
comprobantes_electronicos (
  venta_id
  tipo              -- 'boleta' | 'factura' | 'nota_credito'
  serie, numero, numero_completo   -- ej. 'B001-00000123'
  codigo_tipo_documento
  fecha_emision
  estado_sunat      -- texto libre: descripción del CDR o del error
  ambiente_sunat    -- 'produccion' | 'beta' (según el sunat_server vigente al momento del envío)
  enlace_del_xml, enlace_del_cdr, enlace_del_pdf
  cadena_para_codigo_qr   -- hash del CPE (para el QR del ticket)
  hash_cpe
  soap_request, soap_response   -- opcional, para debug/auditoría
  payload_json, sunat_response_json   -- JSONB, snapshot completo

  -- Solo para notas de crédito:
  referencia_comprobante_id            -- FK al comprobante original
  tipo_nota_credito_id, codigo_tipo_nota_credito
  motivo_nota_credito, descripcion_nota_credito
  documento_modificado_tipo_documento_codigo
  documento_modificado_serie
  documento_modificado_numero
  documento_modificado_numero_completo
  documento_modificado_fecha

  anulado   BOOLEAN
)
```

---

## 3. Cálculo tributario por línea (algoritmo exacto)

Dado un producto con `precio_venta`, `afectacion_igv_codigo`, `porcentaje_igv`,
`incluye_igv`, `icbper_activo`, `factor_icbper`, y una `cantidad`:

```
tipo_afectacion = derivar de afectacion_igv_codigo si afectacion_tipo viene vacío:
    20,21        → EXO
    30..36       → INA
    40           → EXP
    cualquier otro (10, etc.) → GRAV

si tipo_afectacion == GRAV:
    porcentaje_igv = producto.porcentaje_igv (ej. 18)
    incluye_igv    = producto.incluye_igv
si NO es GRAV:
    porcentaje_igv = 0
    incluye_igv    = false   -- exonerado/inafecto no lleva IGV nunca, aunque el flag esté en true

factor_icbper = producto.icbper_activo ? producto.factor_icbper : 0

# --- Precio unitario vs valor unitario ---
si tipo_afectacion == GRAV:
    si incluye_igv (precio_venta ya trae IGV):
        valor_unitario  = precio_venta / (1 + porcentaje_igv/100)     -- 10 decimales
        precio_unitario = precio_venta
        igv_unitario    = precio_unitario - valor_unitario
    si NO incluye_igv (precio_venta es neto, hay que sumar IGV):
        valor_unitario  = precio_venta
        igv_unitario    = valor_unitario * porcentaje_igv/100
        precio_unitario = valor_unitario + igv_unitario
si NO es GRAV (exonerado/inafecto/exportación):
    valor_unitario  = precio_venta
    precio_unitario = precio_venta
    igv_unitario    = 0

# --- Totales de la línea ---
valor_total   = round(valor_unitario * cantidad, 2)
igv           = round(igv_unitario * cantidad, 2)
icbper        = round(factor_icbper * cantidad, 2)
precio_total  = round(precio_unitario * cantidad + icbper, 2)   -- lo que paga el cliente
```

Reglas clave a respetar al portar esto:
- El **ICBPER nunca lleva IGV** y se suma aparte, después del cálculo de IGV.
- `valor_unitario` se calcula con **10 decimales de precisión** (SUNAT es estricto con
  el redondeo de precios unitarios en el XML — usar menos precisión genera diferencias
  de céntimos entre `valor_total` calculado línea por línea y la suma reportada).
- El `valor_total`/`igv`/`precio_total` sí se redondean a 2 decimales.

### 3.1 Totales del comprobante

```
total_op_gravadas   = Σ valor_total de líneas con afectación GRAV
total_op_exoneradas = Σ valor_total de líneas con afectación EXO
total_op_inafectas  = Σ valor_total de líneas con afectación INA
igv                 = Σ igv de todas las líneas
total_antes_impuestos = gravadas + exoneradas + inafectas
total_a_pagar         = total_antes_impuestos + igv   (el ICBPER se suma también al total final que ve el cliente, aparte de estos campos SUNAT)
```

---

## 4. Emisión del comprobante a SUNAT (paso a paso)

### 4.1 Pre-requisitos de configuración (por empresa emisora)

- RUC y razón social configurados.
- Usuario y clave **SOL** (Sunat Operaciones en Línea) — **no** son las credenciales de
  Clave SOL de la persona natural, sino un usuario secundario con el permiso "Enviar
  comprobante electrónico" habilitado en SUNAT.
- Certificado digital `.pfx` vigente, subido al servidor, con su contraseña.
- `sunat_server`: `'1'` = producción (`e-factura.sunat.gob.pe`), `'3'` = beta/homologación
  (`e-beta.sunat.gob.pe`). **Siempre desarrollar y probar contra beta** antes de apuntar a
  producción — beta acepta cualquier certificado/RUC de prueba que SUNAT provee para el
  ambiente de homologación.

### 4.2 Construcción del XML UBL 2.1

Dos tipos de documento raíz, mismo esqueleto general:

- **Boleta / Factura** → elemento raíz `<Invoice>` (namespace UBL Invoice-2).
- **Nota de crédito** → elemento raíz `<CreditNote>` (namespace UBL CreditNote-2), con
  secciones extra: `<cac:DiscrepancyResponse>` (motivo) y `<cac:BillingReference>`
  (referencia al documento que se está corrigiendo/anulando).

Estructura común (elementos obligatorios, en orden):

```
<Invoice> / <CreditNote>
  <ext:UBLExtensions>              -- placeholder vacío, la firma XMLDSig se inyecta aquí después
  <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
  <cbc:CustomizationID>2.0</cbc:CustomizationID>
  <cbc:ProfileID>0101</cbc:ProfileID>      -- solo en Invoice: "Tipo de Operación" (0101 = venta interna)
  <cbc:ID>{serie}-{correlativo}</cbc:ID>
  <cbc:IssueDate>YYYY-MM-DD</cbc:IssueDate>
  <cbc:IssueTime>HH:MM:SS</cbc:IssueTime>
  <cbc:DueDate>...</cbc:DueDate>            -- solo Invoice
  <cbc:InvoiceTypeCode>01|03</cbc:InvoiceTypeCode>   -- solo Invoice (03=boleta, 01=factura)
  <cbc:Note>...</cbc:Note>                   -- solo CreditNote: motivo en texto
  <cbc:DocumentCurrencyCode>PEN</cbc:DocumentCurrencyCode>
  <cbc:LineCountNumeric>N</cbc:LineCountNumeric>   -- solo Invoice

  <cac:DiscrepancyResponse>          -- SOLO CreditNote: código+descripción del motivo (catálogo 09)
  <cac:BillingReference>             -- SOLO CreditNote: referencia al comprobante original (serie-numero + tipo)

  <cac:Signature>                    -- placeholder que apunta a la firma (id "SignatureSP")
  <cac:AccountingSupplierParty>      -- datos del EMISOR (RUC, razón social, dirección, ubigeo)
  <cac:AccountingCustomerParty>      -- datos del CLIENTE (tipo/número doc, razón social, dirección)

  <cac:PaymentTerms>                 -- solo Invoice: forma de pago (Contado/Crédito) + monto a crédito
  <cac:TaxTotal>                     -- IGV total + un <cac:TaxSubtotal> por cada tipo de afectación presente (S/E/O)
  <cac:LegalMonetaryTotal>           -- LineExtensionAmount (base), TaxInclusiveAmount (con IGV), PayableAmount (a pagar)

  <cac:InvoiceLine> / <cac:CreditNoteLine>   -- una por cada línea de venta:
      <cbc:ID>N</cbc:ID>
      <cbc:InvoicedQuantity unitCode="NIU">...</cbc:InvoicedQuantity>   -- "CreditedQuantity" en NC
      <cbc:LineExtensionAmount>...</cbc:LineExtensionAmount>            -- valor_total sin IGV
      <cac:PricingReference>            -- precio de lista con IGV (PriceTypeCode 01)
      <cac:TaxTotal>...</cac:TaxTotal>  -- IGV de la línea + categoría (S/E/O) según afectación
      <cac:Item><cbc:Description>...</cbc:Description><cac:SellersItemIdentification>...</cac:Item>
      <cac:Price><cbc:PriceAmount>...</cbc:PriceAmount></cac:Price>     -- valor_unitario (10 decimales)
</Invoice>
```

Puntos que suelen romper la validación de SUNAT si no se respetan:
- Los importes en XML siempre con **punto decimal** (no coma) y exactamente el número
  de decimales del campo (2 para montos, hasta 10 para precio unitario si es necesario).
- Todos los textos "libres" (razón social, direcciones, descripción de ítem, motivo de
  NC) deben ir envueltos en `<![CDATA[ ... ]]>` para evitar problemas con caracteres
  especiales.
- El `<cac:TaxSubtotal>` de cada categoría (gravado/exonerado/inafecto) **solo se agrega
  si el monto de esa categoría es > 0** — no incluir subtotales en cero.
- `schemeID`, `schemeAgencyName`, `listID`, etc. en los atributos XML son exigidos
  literalmente por el UBL de SUNAT (Catálogo 06 para documentos de identidad, Catálogo
  07 para afectación IGV, Catálogo 01 para tipo de documento) — copiarlos tal cual, no
  son adorno.

### 4.3 Firma digital (XMLDSig)

- Se firma el XML **completo** usando el certificado `.pfx` (RSA) de la empresa.
- El resultado de la firma se inyecta dentro de `<ext:UBLExtensions>` (que se dejó como
  placeholder vacío al construir el XML).
- Es una firma XML-DSig estándar (enveloped signature, canonicalización C14N,
  SHA-1/SHA-256 según lo exigido por SUNAT) — en PHP se implementó con una librería
  propia basada en `xmlseclibs`. **En otro stack, usar la librería estándar de firma
  XMLDSig del lenguaje** (ej. Java: `javax.xml.crypto.dsig`; Node: `xml-crypto`; .NET:
  `System.Security.Cryptography.Xml.SignedXml`; Python: `signxml`) — no hace falta
  reinventar el algoritmo, solo producir el mismo resultado (enveloped signature sobre
  el nodo raíz).
- El nombre del archivo firmado sigue la convención SUNAT:
  `{RUC}-{tipoDocCod}-{serie}-{correlativo8digitos}.XML`
  (ej. `20123456789-03-B001-00000123.XML`).

### 4.4 Empaquetado

- El XML firmado se comprime en un `.ZIP` que contiene **un solo archivo**, con el mismo
  nombre base pero extensión `.XML` dentro del zip.
- El ZIP se codifica en **Base64** para viajar dentro del SOAP.

### 4.5 Envío SOAP (`sendBill`)

Endpoint: `POST {endpoint}` con `Content-Type: text/xml; charset="utf-8"`.

```xml
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:ser="http://service.sunat.gob.pe"
                   xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
  <soapenv:Header>
    <wsse:Security>
      <wsse:UsernameToken>
        <wsse:Username>{RUC}{usuario_SOL}</wsse:Username>   <!-- RUC y usuario SOL CONCATENADOS, sin separador -->
        <wsse:Password Type="...UsernameToken-profile-1.0#PasswordText">{clave_SOL}</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </soapenv:Header>
  <soapenv:Body>
    <ser:sendBill>
      <fileName>{RUC}-{tipoDoc}-{serie}-{correlativo}.ZIP</fileName>
      <contentFile>{ZIP en base64}</contentFile>
    </ser:sendBill>
  </soapenv:Body>
</soapenv:Envelope>
```

Endpoints:

```
Producción: https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService
Beta/Sandbox: https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService
```

### 4.6 Respuesta y CDR

- **Éxito**: la respuesta SOAP trae un nodo `applicationResponse` con un ZIP en
  Base64 → ese ZIP contiene un XML de **CDR (Constancia de Recepción)**, con:
  - `<cbc:ResponseCode>` → `0` = **Aceptado**, `1` = **Observado** (aceptado con
    observaciones), otros valores = distintos niveles de rechazo/error.
  - `<cbc:Description>` → texto descriptivo del resultado.
- **Error**: la respuesta es un SOAP Fault (`faultcode` / `faultstring`) — no hay CDR.
  Guardar el `faultstring` como estado para mostrarlo al usuario.
- Guardar el ZIP del CDR y extraerlo a disco (o storage) para exponerlo como enlace de
  descarga desde el panel de facturación.
- El **hash del CPE** (obtenido al firmar, en el paso 4.3) se usa como cadena del
  **código QR** que se imprime en el ticket/factura (junto con RUC emisor, tipo/serie/
  número, documento del cliente, fecha, moneda y total — es el formato estándar de QR
  SUNAT).

---

## 5. Notas de crédito

Flujo adicional sobre una venta ya emitida:

1. Buscar el comprobante original (`comprobantes_electronicos`) por `venta_id`.
2. Determinar la serie de la NC según el tipo de documento original:
   - Original = Factura (`codigo_tipo_documento = '01'`) → serie **`FC01`**, tipo interno
     `nota_credito_factura`.
   - Original = Boleta (`codigo_tipo_documento = '03'`) → serie **`BC01`**, tipo interno
     `nota_credito_boleta`.
3. Pedir al usuario el **motivo** (catálogo SUNAT 09, ver §2.7) y una descripción libre.
4. Construir las líneas de la NC (normalmente las mismas líneas de la venta original,
   completas o parciales según sea devolución total/parcial).
5. Generar XML `<CreditNote>` (ver §4.2) referenciando el documento original vía
   `<cac:BillingReference>` (serie-número + código de tipo de documento del original).
6. Firmar, empaquetar y enviar igual que una Boleta/Factura (mismo `enviar_sunat()`).
7. Guardar el nuevo comprobante con `referencia_comprobante_id` apuntando al original, y
   copiar los datos del documento modificado (`documento_modificado_*`) para trazabilidad
   y para reimprimir/mostrar el vínculo en el reporte.

---

## 6. Comprobante público / "Mi Comprobante" (opcional pero recomendado)

Por ley, el comprador debe poder consultar su comprobante sin necesidad de credenciales
del sistema del vendedor. Patrón usado:

- Al emitir cualquier venta (ticket, boleta o factura) se genera un **token aleatorio
  no-secuencial** (128 bits, hex) y se guarda en una tabla de resolución pública
  `token → identificador interno de la venta` (en un sistema multi-tenant/multi-sucursal,
  debe incluir también a qué tenant/sucursal pertenece).
- **Nunca exponer un lookup por ID secuencial** — permitiría enumerar y ver comprobantes
  de otros clientes (dato sensible: revela qué compró una persona, especialmente
  delicado en una farmacia).
- Se expone una página pública `/mi-comprobante?t={token}` que resuelve el token,
  carga la venta y muestra/reimprime el comprobante — sin login.
- El mismo token se usa para generar el contenido de un **QR** impreso en el ticket, que
  apunta a esa URL pública.

---

## 7. Checklist para implementar en otro sistema

1. [ ] Modelar las tablas/entidades de §2 (emisor, cliente, producto con campos
   tributarios, venta + detalle, comprobante electrónico, series/correlativos,
   catálogos SUNAT).
2. [ ] Cargar los catálogos SUNAT semilla (tipos de documento de identidad, afectación
   IGV, unidades de medida, monedas, motivos de nota de crédito) — ver tablas de §2.5–2.7
   para los valores mínimos necesarios en un POS.
3. [ ] Implementar el cálculo tributario por línea exactamente como en §3 (ojo con
   precisión decimal y con el manejo de ICBPER aparte del IGV).
4. [ ] Implementar consulta RUC/DNI (§1) contra un proveedor de datos (Factiliza u
   otro), con tu propio token gestionado como secreto de entorno.
5. [ ] Implementar generación de correlativo atómico por tipo de documento (§2.8).
6. [ ] Implementar construcción de XML UBL 2.1 (§4.2) para Invoice y CreditNote.
7. [ ] Implementar firma XMLDSig con el certificado `.pfx` de la empresa (§4.3), usando
   la librería estándar de firma XML del lenguaje elegido.
8. [ ] Implementar empaquetado ZIP + envío SOAP `sendBill` (§4.4–4.5) contra el
   endpoint **beta** primero.
9. [ ] Implementar parseo de CDR y guardar estado/; enlaces de XML/CDR (§4.6).
10. [ ] Implementar flujo de Notas de Crédito (§5).
11. [ ] (Recomendado) Implementar comprobante público vía token no-secuencial + QR (§6).
12. [ ] Probar exhaustivamente contra el ambiente **beta** de SUNAT con el RUC/certificado
    de pruebas que SUNAT provee, antes de apuntar a producción.

---

## 8. Referencias de catálogos SUNAT usados

- Catálogo 01 — Tipo de Documento (Comprobante)
- Catálogo 03 — Unidades de Medida
- Catálogo 06 — Tipo de Documento de Identidad
- Catálogo 07 — Tipo de Afectación del IGV
- Catálogo 09 — Tipo de Nota de Crédito
- Catálogo 10 — Tipo de Nota de Débito
- Catálogo 16 — Tipo de Precio de Venta Unitario
- Catálogo 17 — Tipo de Operación

Estos son los catálogos oficiales publicados por SUNAT para el estándar UBL 2.1 peruano
(Facturación Electrónica - SEE). Cualquier implementación nueva debería validar sus
valores contra la documentación oficial vigente de SUNAT al momento de implementar, ya
que SUNAT actualiza catálogos periódicamente (nuevos códigos de afectación, nuevas
unidades, etc.).
