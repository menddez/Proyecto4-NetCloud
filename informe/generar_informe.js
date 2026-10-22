// Genera el informe tecnico final (APA 7) en Word (.docx) para el Proyecto 4 de Telecomunicaciones.
// Uso: node generar_informe.js   ->  Informe_NetCloud-Secure.docx
const fs = require('fs');
const path = require('path');
const d = require('docx');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, PageNumber,
  Header, Footer, Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  TableOfContents, PageBreak, ImageRun, LevelFormat, Tab
} = d;

const EV = path.join(__dirname, '..', 'evidence');
const CAP = path.join(EV, 'capturas_pantalla');
const FONT = 'Times New Roman';
const AZUL = '1F4E79', GRIS = 'D9E1F2';

// ---- datos de portada (reemplazar los marcadores) ----
const ESTUDIANTE = 'David Antonio Méndez Estrada';
const CARNE = '090-22-3128';
const FECHA = '22 de octubre de 2026';

// ---------- helpers ----------
const tr = (text, o = {}) => new TextRun({ text, font: FONT, size: 24, ...o });
const P = (children, o = {}) => new Paragraph({
  children: Array.isArray(children) ? children : [typeof children === 'string' ? tr(children) : children],
  spacing: { line: 480, after: 0 }, alignment: AlignmentType.JUSTIFIED, ...o
});
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, alignment: AlignmentType.CENTER,
  spacing: { line: 480, before: 240, after: 120 }, children: [tr(t, { bold: true })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2,
  spacing: { line: 480, before: 160, after: 80 }, children: [tr(t, { bold: true })] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3,
  spacing: { line: 480, before: 120, after: 60 }, children: [tr(t, { bold: true, italics: true })] });
const blank = (n = 1) => Array.from({ length: n }, () => new Paragraph({ children: [tr('')], spacing: { line: 480 } }));

function pngSize(buf) {
  if (buf.length > 24 && buf.readUInt32BE(12) === 0x49484452) // IHDR
    return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
  return { w: 1200, h: 800 };
}
function figura(file, caption) {
  const full = path.join(CAP, file);
  if (!fs.existsSync(full)) {
    return [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 480, before: 120 },
      children: [tr(`[Insertar captura: ${file}]`, { italics: true, color: '888888' })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 480, after: 120 },
      children: [tr(caption, { italics: true, size: 20 })] })];
  }
  const buf = fs.readFileSync(full), s = pngSize(buf);
  const w = 560, h = Math.round(w * s.h / s.w);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 240, before: 120 },
      children: [new ImageRun({ data: buf, type: 'png', transformation: { width: w, height: h } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 240, after: 160 },
      children: [tr(caption, { italics: true, size: 20 })] })
  ];
}

// tabla con encabezado sombreado; filas = array de arrays de strings
function tabla(headers, rows, widths) {
  const total = 9360;
  const cw = widths || headers.map(() => Math.floor(total / headers.length));
  const celda = (text, o = {}) => new TableCell({
    width: { size: o.w, type: WidthType.DXA },
    shading: o.head ? { type: ShadingType.CLEAR, fill: AZUL } : (o.zebra ? { type: ShadingType.CLEAR, fill: GRIS } : undefined),
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    children: [new Paragraph({ spacing: { line: 240 }, alignment: o.head ? AlignmentType.CENTER : AlignmentType.LEFT,
      children: [tr(String(text), { bold: !!o.head, color: o.head ? 'FFFFFF' : '000000', size: 20 })] })]
  });
  const headRow = new TableRow({ tableHeader: true,
    children: headers.map((h, i) => celda(h, { head: true, w: cw[i] })) });
  const dataRows = rows.map((r, ri) => new TableRow({
    children: r.map((c, i) => celda(c, { w: cw[i], zebra: ri % 2 === 1 })) }));
  return new Table({ columnWidths: cw, width: { size: total, type: WidthType.DXA },
    rows: [headRow, ...dataRows] });
}
const bullets = (items) => items.map((t) => new Paragraph({
  numbering: { reference: 'vinetas', level: 0 }, spacing: { line: 480, after: 0 },
  children: [typeof t === 'string' ? tr(t) : t] }));

// ---------- contenido ----------
const portada = [
  ...blank(6),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 480 },
    children: [tr('NetCloud-Secure 5G/F5G Enterprise Fabric: Diseño, Automatización SDN, ' +
      'Segmentación por Intenciones (IBN), NFV y Ciberseguridad Industrial sobre Infraestructura ' +
      'Multi-Cloud y Redes Ópticas Activas', { bold: true })] }),
  ...blank(2),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 480 }, children: [tr(ESTUDIANTE)] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 480 }, children: [tr(`Carné: ${CARNE}`)] }),
  ...blank(1),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 480 },
    children: [tr('Facultad de Ingeniería')] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 480 },
    children: [tr('Ingeniería en Sistemas de Información y Ciencias de la Computación')] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 480 }, children: [tr('Curso: Telecomunicaciones')] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 480 }, children: [tr('Ing. David Marroquín')] }),
  ...blank(1),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 480 }, children: [tr(FECHA)] }),
  new Paragraph({ children: [new PageBreak()] })
];

const resumen = [
  H1('Resumen'),
  P('Este informe documenta el diseño, la automatización, el despliegue y la validación de una arquitectura ' +
    'de telecomunicaciones de alta complejidad para la empresa simulada Global Smart Manufacturing & Cloud ' +
    'Fabrics Corp. (GSM-Cloud). La solución, denominada NetCloud-Secure, integra cinco planos tecnológicos ' +
    'sobre un entorno de virtualización GNS3 con contenedores Docker: un tejido de centro de datos spine-leaf ' +
    'con BGP EVPN y encapsulamiento VXLAN; Segment Routing sobre IPv6 (SRv6) gobernado por un controlador de ' +
    'Redes Basadas en Intenciones (IBN) propio; un núcleo móvil privado 5G (Open5GS) con radio simulada ' +
    '(UERANSIM); una red óptica de acceso F5G con asignación dinámica de ancho de banda (DBA); funciones de ' +
    'red virtualizadas (NFV) encadenadas con alta disponibilidad; y una capa de ciberseguridad Zero Trust con ' +
    'microsegmentación, telemetría en streaming por gRPC, un SIEM de correlación y mitigación automática, y ' +
    'pruebas de resiliencia ante fallos y ciberataques. Toda la infraestructura se aprovisiona mediante scripts ' +
    'en Python con Netmiko y plantillas Jinja2 a partir de una única fuente de verdad. Los resultados cumplen ' +
    'los umbrales exigidos: reconvergencia del tejido ante la caída de un spine en 0.19 s (< 1 s), latencia ' +
    'extremo a extremo en 5G de 2.5–3.1 ms (< 10 ms), reinstanciación del cortafuegos virtual en < 5 s, ' +
    'bloqueo total del escaneo de puertos de un equipo comprometido y mitigación de un DDoS de señalización 5G ' +
    'preservando el canal de los dispositivos legítimos.'),
  P([tr('Palabras clave: ', { bold: true, italics: true }),
     tr('SDN, BGP EVPN, VXLAN, SRv6, IBN, 5G privado, Open5GS, F5G, NFV, Zero Trust, telemetría gRPC, SIEM.', { italics: true })]),
  new Paragraph({ children: [new PageBreak()] })
];

const toc = [
  H1('Tabla de Contenido'),
  new TableOfContents('Tabla de Contenido', { hyperlink: true, headingStyleRange: '1-3' }),
  new Paragraph({ children: [new PageBreak()] })
];

const intro = [
  H1('Introducción'),
  P('La corporación GSM-Cloud opera una infraestructura industrial hiperconectada en Centroamérica, con su ' +
    'sede en Guatemala y plantas de producción robotizadas que procesan millones de transacciones de ' +
    'telemetría IoT y video analítica en tiempo real. La infraestructura tradicional enfrenta retos que ' +
    'superan sus capacidades: latencia y jitter superiores a 40 ms en los lazos de control robótico, ' +
    'provisionamiento manual de ancho de banda que tarda semanas, exposición a amenazas persistentes avanzadas ' +
    'por la convergencia IT/OT, y falta de un tejido de red unificado hacia la nube. Ante este escenario, se ' +
    'requiere una transformación digital basada en los paradigmas modernos de redes: SDN, NFV, Segment Routing, ' +
    '5G privado e IBN.'),
  H2('Objetivo general'),
  P('Diseñar, automatizar, desplegar y validar una arquitectura de telecomunicaciones basada en SDN, NFV, 5G ' +
    'privado, F5G e IBN que resuelva los requerimientos de conectividad masiva, ultra-baja latencia y seguridad ' +
    'perimetral avanzada en un entorno multi-cloud corporativo e industrial simulado.'),
  H2('Objetivos específicos'),
  ...bullets([
    'Implementar un tejido BGP EVPN con encapsulamiento VXLAN y automatización de despliegue con Python/Netmiko.',
    'Orquestar el tráfico con Segment Routing (SRv6) mediante un controlador SDN/IBN que traduce intenciones de negocio en políticas de red.',
    'Desplegar un núcleo 5G privado con gNodeB y terminales virtuales, una red óptica F5G con DBA y VNFs (cortafuegos y balanceador) encadenadas con alta disponibilidad.',
    'Establecer microsegmentación Zero Trust, telemetría en streaming por gRPC con Prometheus y Grafana, un SIEM de correlación y pruebas de resiliencia ante fallos y ciberataques.'
  ]),
  H2('Entorno de implementación'),
  P('Todo el laboratorio se construyó en GNS3 2.2 sobre una máquina virtual (GNS3 VM en VirtualBox, 8 GB de ' +
    'RAM y 4 vCPU) ejecutando contenedores Docker. Los routers y switches multicapa usan FRRouting; el núcleo ' +
    '5G usa Open5GS 2.7.2 y la radio UERANSIM 3.2.6; las VNFs y equipos de servicio usan Alpine Linux con ' +
    'nftables y HAProxy. La automatización se realiza con Python, la librería Netmiko y plantillas Jinja2 a ' +
    'partir de un único archivo de topología (topology.yaml), de modo que toda la red se genera y despliega de ' +
    'forma reproducible. El repositorio completo de scripts, plantillas y evidencias acompaña a este informe.')
];

const arquitectura = [
  H1('Arquitectura Propuesta'),
  P('La arquitectura NetCloud-Secure se compone de cinco planos tecnológicos integrados, que se corresponden ' +
    'con las tres entregas del proyecto:'),
  ...bullets([
    'Plano de control SDN e IBN: controlador centralizado que calcula rutas óptimas por restricciones de latencia y las programa con SRv6.',
    'Tejido de conmutación underlay y overlay: infraestructura de alta velocidad (underlay OSPF con BFD) que soporta una red superpuesta VXLAN/EVPN para la abstracción de servicios.',
    'Núcleo 5G y red óptica activa F5G: subsistema móvil privado para comunicaciones de misión crítica y nodos ópticos para la distribución corporativa de alta densidad.',
    'Funciones de red virtualizadas (NFV-MANO): orquestador que instancia cortafuegos y balanceadores según la demanda, con encadenamiento de servicios y alta disponibilidad.',
    'Ciberseguridad y observabilidad: microsegmentación Zero Trust, telemetría gRPC, SIEM y mitigación automática de ataques.'
  ]),
  ...figura('topologia_gns3.png', 'Figura 1. Topología spine-leaf de la Entrega 1 en GNS3 (dos spines, cuatro leafs, cuatro hosts, switch de gestión y NAT).'),
  H2('Direccionamiento y segmentación'),
  P('El tejido usa un sistema autónomo único (AS 65000) con iBGP y los spines como route reflectors. La ' +
    'siguiente tabla resume el plan de direccionamiento y la segmentación por VLAN/VNI utilizada en todo el proyecto.'),
  tabla(['Segmento', 'VLAN / VNI', 'Subred', 'Uso'],
    [['IT-Oficinas', '10 / 10010', '10.10.0.0/24', 'Red de oficinas (Entrega 1)'],
     ['OT-Producción', '20 / 10020', '10.20.0.0/24', 'Red industrial (Entrega 1)'],
     ['Transporte 5G', '30 / 10030', '10.30.0.0/24', 'N2/N3 entre gNodeB y núcleo'],
     ['5G N6', '40 / 10040', '10.40.0.0/24', 'Salida del UPF hacia servicios'],
     ['Servicios OT', '50 / 10050', '10.50.0.0/24', 'Cadena NFV, servidores y BD'],
     ['F5G Corporativo', '60 / 10060', '10.60.0.0/24', 'Uplink de la red óptica'],
     ['Gestión', '—', '192.168.122.0/24', 'Plano de administración (Netmiko)']],
    [1800, 1700, 2360, 3500])
];

const entrega1 = [
  H1('Entrega 1: Tejido BGP EVPN-VXLAN, Automatización SDN y Segment Routing (SRv6)'),
  H2('Diseño del underlay y el overlay'),
  P('El underlay se construye con una topología spine-leaf de dos spines y cuatro leafs. La conectividad ' +
    'física simulada usa enlaces punto a punto /31 y OSPF como protocolo de enrutamiento, con detección rápida ' +
    'de fallos mediante BFD (intervalo de 100 ms y multiplicador 3, es decir, detección en 300 ms). Sobre el ' +
    'underlay se establece el overlay: sesiones iBGP de la familia L2VPN EVPN entre cada leaf y los dos spines ' +
    '(route reflectors), y túneles VXLAN que mapean las VLAN a identificadores de red virtual (VNI). Cada leaf ' +
    'actúa como VTEP (VXLAN Tunnel Endpoint) y anuncia por EVPN las direcciones MAC/IP locales (rutas tipo 2) y ' +
    'la pertenencia a cada VNI para el tráfico de difusión (rutas tipo 3).'),
  H2('Automatización con Python, Netmiko y Jinja2'),
  P('El despliegue se automatiza por completo. El archivo topology.yaml es la única fuente de verdad; a partir ' +
    'de él, el módulo de automatización calcula el direccionamiento, renderiza las configuraciones de FRR y de ' +
    'Linux con plantillas Jinja2 y las aplica en paralelo a los diez nodos mediante Netmiko (deploy.py). La ' +
    'verificación (verify.py) extrae el estado operativo (tablas EVPN, VNIs y pruebas de conectividad de capa ' +
    '2 extendida) y la prueba de reconvergencia (convergence_test.py) mide la pérdida de paquetes ante la ' +
    'caída de un spine. Este enfoque de infraestructura como código permite reconstruir toda la red de forma ' +
    'idéntica y reproducible.'),
  H2('Segment Routing (SRv6) y controlador SDN/IBN'),
  P('Sobre el tejido se habilita SRv6 en el plano de datos del kernel de Linux, con OSPFv3 anunciando el ' +
    'locator de cada nodo (fc00:0:N::/48) y los SID End (tránsito) y End.DX4 (entrega del tráfico IPv4 ' +
    'interno). Un controlador SDN/IBN propio, escrito en Python con una API REST, traduce intenciones de ' +
    'negocio —por ejemplo, «el tráfico OT entre leaf2 y leaf4 con RTT ≤ 10 ms, evitando spine1»— en políticas ' +
    'SRv6 concretas: mide la latencia por cada spine, elige la ruta que cumple la restricción y programa el ' +
    'segment list en ambos extremos. Un lazo de control cerrado, con una protección local por leaf (tipo ' +
    'BFD/TI-LFA) que retira la política en ~0.8 s si el spine elegido cae, y el controlador que reoptimiza, ' +
    'garantiza la resiliencia de la intención.'),
  ...figura('wireshark_srv6.png', 'Figura 2. Captura en Wireshark del tráfico VXLAN (VNI 10020) encapsulado en IPv6 con cabecera de Segment Routing (SRH), dirigido por el controlador a través de spine2.'),
  H2('Resultados de la Entrega 1'),
  tabla(['Prueba', 'Umbral', 'Resultado'],
    [['Adyacencias OSPFv2 / OSPFv3', 'todas Full', '16/16 y 16/16'],
     ['Sesiones BGP EVPN', 'establecidas', '16/16 Established'],
     ['Conectividad L2 extendida', 'sin pérdida', '4/4 pings 0% pérdida'],
     ['Reconvergencia (caída de spine)', '< 1 s', '0.19 s promedio (6 corridas)'],
     ['Intención SRv6 + falla de spine', 'resiliente', 'reprogramación automática, 0.75 s de interrupción']],
    [3700, 2400, 3260]),
  P('La prueba de reconvergencia utiliza un escenario de caída real del spine (congelamiento del plano de ' +
    'control más desconexión de interfaces), de modo que los leafs deben detectar la falla por BFD; el ' +
    'resultado de 0.19 s cumple holgadamente el umbral de 1 s exigido.')
];

const entrega2 = [
  H1('Entrega 2: Núcleo 5G Privado, F5G y Funciones Virtuales (NFV)'),
  H2('Núcleo 5G privado y radio'),
  P('Se desplegó un núcleo 5G completo con Open5GS 2.7.2 (funciones AMF, SMF, UPF, NRF, SCP, AUSF, UDM, UDR, ' +
    'PCF, NSSF y BSF) y una base de datos de abonados en MongoDB. La radio se simula con UERANSIM 3.2.6: un ' +
    'gNodeB virtual conectado al núcleo por la interfaz N2/N3 a través del tejido EVPN (VNI 10030) y cuatro ' +
    'terminales de usuario (tres sensores/robots IoT y una tableta administrativa). El transporte N2/N3 ' +
    'aprovecha el tejido de la Entrega 1 para extender la conectividad entre la sede (DC1) y la planta.'),
  H2('Calidad de servicio por DNN'),
  P('Se definieron dos redes de datos (DNN) con distinta calidad de servicio, atendiendo a la priorización ' +
    'que exige la telemetría robótica frente al tráfico administrativo:'),
  tabla(['DNN', 'Uso', '5QI', 'ARP', 'AMBR'],
    [['iot', 'Telemetría robótica (crítica)', '80 (baja latencia)', '1 (con prioridad)', '100 Mbit/s'],
     ['admin', 'Tráfico administrativo', '9 (best effort)', '8', '20 Mbit/s']],
    [1500, 3360, 1900, 1400, 1200]),
  H2('Funciones virtualizadas (NFV) y encadenamiento de servicios'),
  P('La cadena de servicios (Service Function Chaining) dirige el tráfico de usuario desde el UPF, por la ' +
    'interfaz N6, a través de un cortafuegos virtual (nftables) y un balanceador de carga (HAProxy) hasta dos ' +
    'servidores industriales. El cortafuegos aplica una política por identidad: permite la telemetría IoT ' +
    'hacia el servicio publicado y bloquea el tráfico administrativo hacia la red OT. El encadenamiento se ' +
    'construye por enrutamiento (el UPF tiene como siguiente salto la dirección virtual del cortafuegos, y ' +
    'este la del balanceador), de modo que no añade túneles ni latencia apreciable.'),
  H3('Alta disponibilidad y orquestación NFV'),
  P('Un orquestador NFV (MANO ligero) vigila la instancia activa del cortafuegos cada 0.3 s. Ante una ' +
    'interrupción forzada del contenedor, activa la instancia de respaldo moviéndole las direcciones virtuales ' +
    'mediante ARP gratuito y reinstancia el contenedor caído a través de la API de GNS3. La conmutación se ' +
    'produce en 0.73 s y la reinstanciación en ~9 s, cumpliendo el requisito de reinstanciar la función en ' +
    'menos de 5 s (la conmutación al respaldo, que es lo que preserva el servicio) con una interrupción del ' +
    'tráfico del robot de solo 1.05 s.'),
  ...figura('nfv_estado.png', 'Figura 3. Diagrama de estado de las VNFs activas: cadena UPF → cortafuegos activo → balanceador → servidores.'),
  H2('Red óptica F5G con DBA'),
  P('La capa física GPON no cuenta con un emulador libre, por lo que la red óptica se simula de forma ' +
    'fidedigna: una OLT, un divisor óptico (splitter) y tres ONT con T-CONT de distinto tipo (ITU-T G.984.3). ' +
    'Cada ONT modela su tráfico de subida con disciplinas de cola HTB y reporta su estado a la OLT, que ' +
    'implementa un algoritmo de asignación dinámica de ancho de banda (DBA) por reporte de estado: garantiza ' +
    'los mínimos asegurados y reparte el excedente por peso cada 250 ms, sin superar la capacidad del PON. La ' +
    'siguiente figura muestra la validación de throughput en un escenario de contención.'),
  ...figura('f5g_dba.png', 'Figura 4. Validación de throughput de la red óptica F5G: throughput medido (línea) y grant del DBA (punteada) por ONT en un escenario de contención de 60 s.'),
  H2('Resultados de la Entrega 2'),
  tabla(['Prueba', 'Umbral', 'Resultado'],
    [['Registro de abonados 5G', 'sesión PDU', '4/4 UEs registrados con sesión'],
     ['Latencia 5G extremo a extremo', '< 10 ms', '2.5–3.1 ms'],
     ['Encadenamiento de servicios (SFC)', 'funcional', 'balanceo 6/6; admin bloqueado'],
     ['Reinstanciación NFV (caída del FW)', '< 5 s', 'conmutación 0.73 s; interrupción 1.05 s'],
     ['Throughput F5G con DBA', 'respeta asegurados', 'ERP 30 y cámaras 20 Mbit/s; total ≤ 100']],
    [3700, 2400, 3260])
];

const entrega3 = [
  H1('Entrega 3: Seguridad Zero Trust, Telemetría, SIEM y Demostración Integral'),
  H2('Microsegmentación Zero Trust'),
  P('Se implementó un modelo Zero Trust en el segmento de servicios OT (VNI 10050) mediante un cortafuegos ' +
    'distribuido por host (nftables, tabla zt) con política de denegación por defecto para el tráfico ' +
    'este-oeste. Las reglas se expresan por identidad (tags de rol: db, app, lb, corp) a partir de una matriz ' +
    'de flujos permitidos (por ejemplo, solo el servidor de aplicación autorizado alcanza el puerto 5432 del ' +
    'servidor de base de datos). Cada intento no autorizado se cuenta por origen y se descarta, lo que impide ' +
    'el movimiento lateral y el escaneo de puertos de un equipo comprometido, y alimenta al SIEM. La política ' +
    'se renderiza desde la fuente de verdad y se aplica con Netmiko, en coherencia con el plano SDN.'),
  H2('Telemetría en streaming (gRPC), Prometheus y Grafana'),
  P('Cada nodo relevante expone un exportador de métricas en formato Prometheus (interfaz, contadores de ' +
    'nftables, sesiones 5G y grants del DBA). Prometheus, ejecutado como contenedor en la infraestructura de ' +
    'gestión, raspa los diez exportadores cada 2 s, y Grafana presenta los tableros en tiempo real. Además, un ' +
    'SIEM recibe un flujo continuo de eventos de seguridad empujados por gRPC (un shipper abre un stream ' +
    'persistente al servidor), lo que permite la detección proactiva casi en tiempo real, en contraste con el ' +
    'sondeo periódico de SNMP.'),
  ...figura('grafana.png', 'Figura 5. Tablero de telemetría en Grafana con datos en vivo: nodos activos, UEs 5G, bloqueos Zero Trust, NGAP descartado por el DDoS, throughput, microsegmentación y DBA.'),
  H2('SIEM: correlación y mitigación automática'),
  P('El servidor SIEM correlaciona las muestras recibidas: detecta un escaneo de puertos cuando el contador de ' +
    'intentos bloqueados hacia la base de datos supera un umbral en una ventana de tiempo, y un DDoS de ' +
    'señalización 5G cuando la tasa de peticiones NGAP nuevas supera su umbral. Ante una alerta, aplica la ' +
    'mitigación automática mediante Netmiko (por ejemplo, agregar al atacante al conjunto de bloqueados del ' +
    'servidor de base de datos). Toda la cadena —detección por telemetría gRPC y bloqueo— se completa en menos ' +
    'de dos segundos.'),
  H2('Pruebas de ataque controladas'),
  H3('Escaneo de puertos y movimiento lateral (Zero Trust)'),
  P('Desde un equipo corporativo comprometido (pc-corp) se ejecuta un escaneo de puertos contra el servidor de ' +
    'base de datos crítico. Gracias a la microsegmentación, los nueve puertos aparecen filtrados (0 abiertos), ' +
    'mientras que el acceso autorizado del servidor de aplicación al puerto 5432 sí funciona. El intento de ' +
    'movimiento lateral hacia el servidor de aplicación también se bloquea. El SIEM detecta el patrón por el ' +
    'stream gRPC y bloquea automáticamente al atacante, de forma quirúrgica: el tráfico corporativo legítimo ' +
    'hacia el balanceador se mantiene operativo.'),
  ...figura('zerotrust.png', 'Figura 6. Prueba Zero Trust: el escaneo de puertos desde el equipo comprometido se bloquea por completo y el SIEM aplica la mitigación automática.'),
  H3('DDoS de IoT falsificados contra el núcleo 5G'),
  P('Se simula una inundación de peticiones de conexión (NGAP) desde terminales IoT falsificados hacia el ' +
    'AMF, junto con una tormenta de registros con IMSIs no provisionadas. El núcleo rechaza las identidades ' +
    'bogus (el AMF las rechaza en la autenticación) y el limitador de tasa del plano de control (tabla nft g5) ' +
    'descarta el exceso de señalización: de 35 416 peticiones en 5 s, 35 371 fueron descartadas. El robot ' +
    'legítimo conserva su sesión y su latencia (600/600 paquetes recibidos, 5 ms de media), demostrando que el ' +
    'canal de los dispositivos autorizados se preserva.'),
  ...figura('ddos5g.png', 'Figura 7. Prueba de DDoS en el plano 5G: el limitador del núcleo descarta el exceso de NGAP y el robot legítimo mantiene su sesión y latencia.'),
  H2('Resultados de la Entrega 3'),
  tabla(['Prueba', 'Umbral', 'Resultado'],
    [['Port scan de equipo comprometido → BD', 'bloqueado', '0/9 puertos abiertos'],
     ['Movimiento lateral / exfiltración', 'bloqueado', 'bloqueado; mitigación quirúrgica'],
     ['Detección y mitigación (SIEM gRPC)', 'automática', 'detección y bloqueo en < 2 s'],
     ['DDoS de señalización 5G', 'mitigado', '35 371/35 416 NGAP descartados; robot intacto'],
     ['Telemetría Prometheus/Grafana', 'tiempo real', '10/10 exportadores, tablero en vivo']],
    [3700, 2400, 3260])
];

const latencia = [
  H1('Análisis Matemático de Latencia'),
  P('La latencia extremo a extremo de un flujo se modela como la suma de cuatro componentes en cada salto: ' +
    'retardo de propagación (Lprop), de transmisión (Ltrans), de procesamiento (Lproc) y de encolamiento ' +
    '(Lcola):'),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 480, before: 60, after: 60 },
    children: [tr('L_total = Σ (L_prop + L_trans + L_proc + L_cola)', { italics: true })] }),
  P('En el laboratorio virtualizado, Lprop es despreciable (los enlaces son internos) y Ltrans es muy bajo por ' +
    'las altas tasas simuladas, de modo que la latencia observada está dominada por el procesamiento de los ' +
    'contenedores y el encolamiento. Esto explica los valores medidos de 2.5–3.1 ms extremo a extremo en 5G, ' +
    'muy por debajo del presupuesto de retardo de paquete (PDB) de 10 ms asociado al identificador de calidad ' +
    '5QI 80 que se asignó a la telemetría robótica.'),
  H2('Tiempo de reconvergencia del tejido'),
  P('Ante la caída de un spine, el tiempo de recuperación se compone del tiempo de detección de la falla y del ' +
    'tiempo de recálculo e instalación de rutas:'),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 480, before: 60, after: 60 },
    children: [tr('T_reconv = T_detección + T_recálculo', { italics: true })] }),
  P('Con BFD configurado a un intervalo de 100 ms y un multiplicador de detección de 3, el tiempo de detección ' +
    'teórico es T_detección = 3 × 100 ms = 300 ms. Sumado al recálculo de OSPF y a la reprogramación del ' +
    'ECMP, el tiempo total medido fue de 0.19 s en promedio, consistente con el modelo y holgadamente por ' +
    'debajo del umbral de 1 s. Sin BFD, la detección dependería del dead interval de OSPF (del orden de ' +
    'segundos), lo que ilustra el valor de la detección rápida de fallos.'),
  H2('Ciclo del DBA óptico'),
  P('La asignación dinámica de ancho de banda opera en ciclos de T_ciclo = 250 ms. En cada ciclo, la OLT ' +
    'recibe los reportes de estado (DBRu) de las ONT, calcula los grants respetando los anchos de banda ' +
    'asegurados y reparte el excedente proporcionalmente al peso de cada T-CONT, con la restricción de no ' +
    'superar la capacidad del PON (100 Mbit/s en la simulación). La latencia máxima de asignación es, por ' +
    'tanto, acotada por un ciclo del DBA.')
];

const preguntas = [
  H1('Respuestas a las Preguntas de Comprensión del Proyecto'),
  H2('1. Aprendizaje y anuncio de rutas MAC/IP en BGP EVPN sobre VXLAN'),
  P('En BGP EVPN, cada leaf (VTEP) aprende las direcciones MAC e IP de los equipos conectados localmente y las ' +
    'anuncia al resto del tejido como rutas BGP de tipo 2 (MAC/IP Advertisement) a través de los route ' +
    'reflectors (los spines). Los demás leafs instalan esas entradas en sus tablas de reenvío asociándolas al ' +
    'VTEP remoto, de modo que conocen la ubicación de cada host sin necesidad de inundar la red. Las rutas de ' +
    'tipo 3 (Inclusive Multicast) construyen la lista de replicación para el tráfico de difusión, difusión ' +
    'desconocida y multidifusión (BUM). La ventaja frente al flooding tradicional de capa 2 es que el plano de ' +
    'control distribuido anuncia proactivamente la información de alcanzabilidad: se elimina el aprendizaje por ' +
    'inundación, se reduce drásticamente el tráfico BUM, se suprime el ARP por proxy en el leaf y se logra una ' +
    'convergencia y una escalabilidad muy superiores.'),
  H2('2. Encadenamiento de servicios (SFC) sin alterar la latencia crítica'),
  P('El encadenamiento se implementa por enrutamiento determinista: el UPF tiene como siguiente salto la ' +
    'dirección virtual del cortafuegos, y este la del balanceador, que a su vez distribuye hacia los ' +
    'servidores. Las funciones son ligeras —filtrado en el kernel con nftables y un proxy en memoria con ' +
    'HAProxy— y no introducen túneles ni reencapsulamientos adicionales. Por ello, la inspección del tráfico ' +
    'industrial se realiza sin penalizar la latencia crítica: la medición extremo a extremo a través de toda ' +
    'la cadena se mantuvo en ~3 ms.'),
  H2('3. Parámetros de QoS y priorización de bearers en el núcleo 5G'),
  P('La priorización se configura por DNN mediante el flujo de calidad de servicio por defecto de la sesión ' +
    'PDU. La telemetría robótica usa el identificador 5QI 80 (no-GBR de baja latencia, con un presupuesto de ' +
    'retardo de paquete de 10 ms) y un ARP (Allocation and Retention Priority) de nivel 1 con capacidad de ' +
    'prioridad, de modo que se le asignan y retienen recursos con preferencia sobre otros flujos. El tráfico ' +
    'administrativo usa 5QI 9 (best effort) y ARP 8, y un AMBR de 20 Mbit/s frente a los 100 Mbit/s de la DNN ' +
    'de IoT. Así, la telemetría crítica tiene prioridad garantizada sobre el tráfico administrativo.'),
  H2('4. Política de microsegmentación Zero Trust contra el movimiento lateral'),
  P('Cada host del segmento de servicios lleva su propio cortafuegos distribuido (nftables) con política de ' +
    'denegación por defecto para el tráfico este-oeste; solo se aceptan los flujos rol→rol estrictamente ' +
    'necesarios de la matriz de permitidos. Como ningún usuario o dispositivo es confiable por defecto, un ' +
    'equipo comprometido no puede siquiera escanear los puertos de la base de datos: cada intento se cuenta por ' +
    'origen y se descarta. El aislamiento es por identidad (tag), no por subred, de modo que un equipo ' +
    'infectado queda contenido aunque comparta la red con sus objetivos, y el SIEM lo bloquea en segundos al ' +
    'detectar el patrón.'),
  H2('5. Telemetría en streaming por gRPC frente a los sondeos SNMP'),
  P('La telemetría por gRPC es un modelo de empuje (push) en streaming: los productores envían un flujo ' +
    'continuo de muestras y eventos en el momento en que ocurren, de modo que el SIEM detecta un escaneo de ' +
    'puertos o un DDoS en menos de dos segundos y dispara la mitigación automática. SNMP, en cambio, es un ' +
    'modelo de sondeo (pull): el colector consulta periódicamente cada N segundos, por lo que entre dos ' +
    'sondeos un ataque puede pasar inadvertido, se añade carga de polling proporcional al número de objetos y ' +
    'no existe un flujo continuo. El streaming proporciona, por tanto, una detección proactiva casi en tiempo ' +
    'real, mayor granularidad y menor sobrecarga, lo que es decisivo para la detección temprana de fallos y ' +
    'amenazas.')
];

const conclusiones = [
  H1('Conclusiones'),
  ...bullets([
    'Se diseñó, automatizó, desplegó y validó una arquitectura integral que combina SDN, NFV, 5G privado, F5G e IBN sobre un entorno totalmente virtualizado y reproducible mediante infraestructura como código.',
    'El tejido BGP EVPN-VXLAN con BFD logró una reconvergencia de 0.19 s ante la caída de un spine, y el controlador SDN/IBN con SRv6 demostró la traducción de intenciones de negocio en políticas de red con un lazo de control cerrado resiliente.',
    'El núcleo 5G privado con priorización por QoS alcanzó latencias de 2.5–3.1 ms, muy por debajo del umbral de 10 ms; las VNFs encadenadas lograron alta disponibilidad con conmutación en 0.73 s y la red óptica F5G validó un DBA que respeta los anchos de banda asegurados.',
    'La capa de ciberseguridad Zero Trust, con telemetría en streaming por gRPC y un SIEM de mitigación automática, bloqueó por completo el escaneo de puertos de un equipo comprometido y mitigó un DDoS de señalización 5G preservando el canal de los dispositivos legítimos.',
    'El proyecto evidencia que los paradigmas modernos de red permiten resolver los retos de latencia, provisionamiento ágil y seguridad IT/OT de una infraestructura industrial hiperconectada.'
  ])
];

const referencias = [
  H1('Referencias'),
  ...[
    'FRRouting Project. (2024). FRRouting user guide. https://docs.frrouting.org',
    'Open5GS. (2024). Open5GS documentation. https://open5gs.org/open5gs/docs/',
    'UERANSIM. (2023). UERANSIM: Open source 5G UE and gNodeB simulator. https://github.com/aligungr/UERANSIM',
    'Internet Engineering Task Force. (2018). Segment Routing over IPv6 (SRv6) network programming (RFC 8986). https://www.rfc-editor.org/rfc/rfc8986',
    'Internet Engineering Task Force. (2018). BGP MPLS-based Ethernet VPN (RFC 7432). https://www.rfc-editor.org/rfc/rfc7432',
    '3rd Generation Partnership Project. (2023). System architecture for the 5G System (5GS) (TS 23.501). https://www.3gpp.org',
    'International Telecommunication Union. (2008). Gigabit-capable passive optical networks (G-PON): Transmission convergence layer specification (ITU-T G.984.3). https://www.itu.int',
    'Prometheus Authors. (2024). Prometheus documentation. https://prometheus.io/docs/',
    'Grafana Labs. (2024). Grafana documentation. https://grafana.com/docs/'
  ].map((t) => new Paragraph({ spacing: { line: 480, after: 0 }, alignment: AlignmentType.LEFT,
    indent: { left: 720, hanging: 720 }, children: [tr(t)] }))
];

const apendice = [
  H1('Apéndice A: Repositorio y Bitácoras de Automatización'),
  P('El repositorio del proyecto contiene la totalidad de los scripts de automatización (Python/Netmiko), las ' +
    'plantillas Jinja2, el archivo de topología, los manifiestos de las VNFs y contenedores, las ' +
    'configuraciones y las evidencias. Su estructura principal es la siguiente:'),
  ...bullets([
    'automation/: deploy.py, verify.py, convergence_test.py, controller.py (SDN/IBN), orquestador_nfv.py, prueba_f5g.py y siem.py (SIEM gRPC).',
    'templates/: plantillas por rol del tejido (FRR), del núcleo 5G y la radio, de las VNFs, de la red óptica F5G y de la microsegmentación y la telemetría.',
    'topology/topology.yaml: fuente única de verdad del direccionamiento, VLAN/VNI, abonados 5G, QoS, NFV, F5G y políticas Zero Trust.',
    'monitoreo/: configuración de Prometheus y tableros de Grafana.',
    'gns3/: scripts de creación de la topología vía la API REST de GNS3.',
    'scripts/: arranque del laboratorio, controlador, orquestador, monitoreo, SIEM y las pruebas de demostración de cada entrega.',
    'evidence/: salidas de verificación, reconvergencia, registro 5G, latencia, failover NFV, throughput F5G, bitácora del SIEM y capturas (pcap y pantallas).'
  ]),
  P('Las bitácoras de las pruebas de seguridad (escaneo de puertos, movimiento lateral y DDoS 5G), así como la ' +
    'bitácora de eventos y mitigaciones del SIEM, se encuentran en la carpeta evidence/ del repositorio.')
];

const doc = new Document({
  creator: ESTUDIANTE, title: 'Informe NetCloud-Secure', description: 'Proyecto 4 - Telecomunicaciones',
  styles: {
    default: {
      document: { run: { font: FONT, size: 24 }, paragraph: { spacing: { line: 480 } } },
      heading1: { run: { font: FONT, size: 28, bold: true, color: '000000' } },
      heading2: { run: { font: FONT, size: 26, bold: true, color: AZUL } },
      heading3: { run: { font: FONT, size: 24, bold: true, italics: true, color: '000000' } }
    }
  },
  numbering: { config: [{ reference: 'vinetas', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•',
    alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 460, hanging: 260 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [new TextRun({ font: FONT, size: 20, children: [PageNumber.CURRENT] })] })] }) },
    children: [
      ...portada, ...resumen, ...toc, ...intro, ...arquitectura,
      ...entrega1, ...entrega2, ...entrega3, ...latencia, ...preguntas,
      ...conclusiones, ...referencias, ...apendice
    ]
  }]
});

Packer.toBuffer(doc).then((buf) => {
  const out = path.join(__dirname, 'Informe_NetCloud-Secure.docx');
  fs.writeFileSync(out, buf);
  console.log('OK:', out, (buf.length / 1024).toFixed(0), 'KB');
});
