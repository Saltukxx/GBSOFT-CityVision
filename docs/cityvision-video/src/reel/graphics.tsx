import {interpolate, useCurrentFrame} from "remotion";
import {C, FONT, clamp, ease, inAt} from "./theme";

/* ================================================================== */
/* 1. Tespit anotasyonu                                                */
/* ================================================================== */

export type Box = {x: number; y: number; w: number; h: number};

const bracket = (b: Box, l: number) =>
  `M ${b.x} ${b.y + l} V ${b.y} H ${b.x + l}` +
  ` M ${b.x + b.w - l} ${b.y} H ${b.x + b.w} V ${b.y + l}` +
  ` M ${b.x + b.w} ${b.y + b.h - l} V ${b.y + b.h} H ${b.x + b.w - l}` +
  ` M ${b.x + l} ${b.y + b.h} H ${b.x} V ${b.y + b.h - l}`;

/**
 * Gerçek bir tespit arayüzü gibi davranır: önce ince arama kutusu belirir,
 * sonra köşeler kilitlenir, en son sınıf etiketi + skor açılır.
 * Neon parıltı yok — ince çizgi, net köşe, okunur etiket.
 */
export const Annotation: React.FC<{
  box: Box;
  label: string;
  score?: string;
  meta?: string;
  color?: string;
  delay?: number;
  /** Etiketi kutunun altına koyar (kutu üstte yer yoksa). */
  labelBelow?: boolean;
  /** İkincil, etiketsiz kutular (aynı karede birden çok nesne). */
  extra?: Box[];
}> = ({box, label, score, meta, color = C.accent, delay = 0, labelBelow = false, extra = []}) => {
  const frame = useCurrentFrame();
  const seek = inAt(frame, delay, 9); // arama kutusu
  const lock = inAt(frame, delay + 6, 12); // köşe kilidi
  const tag = inAt(frame, delay + 13, 10); // etiket
  const l = Math.min(46, box.w * 0.22, box.h * 0.22);
  const tagW = Math.min(
    Math.max(340, label.length * 17 + 150, (meta?.length ?? 0) * 11.6 + 52),
    box.w + 140,
  );
  // Teknik satır varsa etiket iki satırlık tek bir plakete dönüşür.
  const tagH = meta ? 80 : 48;
  const tagY = labelBelow ? box.y + box.h + 14 : box.y - (tagH + 14);

  return (
    <svg viewBox="0 0 1080 1920" style={{position: "absolute", inset: 0, width: "100%", height: "100%", zIndex: 34}}>
      {/* ikincil nesneler */}
      {extra.map((e, i) => {
        const p = inAt(frame, delay + 14 + i * 6, 14);
        return (
          <g key={`e${i}`} opacity={p * 0.62}>
            <rect x={e.x} y={e.y} width={e.w} height={e.h} fill="none" stroke={color} strokeWidth="1.5" strokeDasharray="6 8" />
            <path d={bracket(e, Math.min(22, e.w * 0.2))} fill="none" stroke={color} strokeWidth="3" />
          </g>
        );
      })}

      {/* arama kutusu: dışarıdan içeri daralır */}
      <rect
        x={box.x - (1 - seek) * 26}
        y={box.y - (1 - seek) * 26}
        width={box.w + (1 - seek) * 52}
        height={box.h + (1 - seek) * 52}
        fill="none"
        stroke={color}
        strokeOpacity={0.42 * seek}
        strokeWidth="1.5"
        strokeDasharray="7 9"
      />
      <rect x={box.x} y={box.y} width={box.w} height={box.h} fill={color} fillOpacity={0.026 * lock} />

      {/* kilitlenen köşeler */}
      <path
        d={bracket(box, l)}
        fill="none"
        stroke={color}
        strokeWidth="4"
        strokeLinecap="butt"
        pathLength="1"
        strokeDasharray="1"
        strokeDashoffset={1 - lock}
      />

      {/* kenar ölçü çentikleri — ölçüm yapılıyor hissi */}
      <g opacity={lock * 0.5} stroke={color} strokeWidth="1.5">
        <path d={`M ${box.x + box.w / 2 - 14} ${box.y} h 28`} />
        <path d={`M ${box.x + box.w / 2 - 14} ${box.y + box.h} h 28`} />
        <path d={`M ${box.x} ${box.y + box.h / 2 - 14} v 28`} />
        <path d={`M ${box.x + box.w} ${box.y + box.h / 2 - 14} v 28`} />
      </g>

      {/* sınıf etiketi — tek plaket: sınıf + skor, altında teknik satır */}
      <g opacity={tag} transform={`translate(${box.x}, ${tagY})`}>
        <path
          d={`M 0 0 H ${tagW - 22} L ${tagW} 24 L ${tagW - 22} 48 V ${tagH} H 0 Z`}
          fill="rgba(5,7,14,.90)"
          stroke={color}
          strokeWidth="1.5"
        />
        <rect x="0" y="0" width="4" height={tagH} fill={color} />
        <text x="20" y="31" fill={C.text} fontFamily={FONT.sans} fontSize="24" fontWeight="600" letterSpacing="0.6">
          {label}
        </text>
        {score ? (
          <text x={tagW - 40} y="31" textAnchor="end" fill={color} fontFamily={FONT.mono} fontSize="22" fontWeight="600">
            {score}
          </text>
        ) : null}
        {meta ? (
          <>
            <line x1="0" y1="48" x2={tagW} y2="48" stroke={color} strokeOpacity="0.35" strokeWidth="1" />
            <text x="20" y="69" fill={C.dim} fontFamily={FONT.mono} fontSize="17" letterSpacing="1.3">
              {meta}
            </text>
          </>
        ) : null}
      </g>
    </svg>
  );
};

/* ================================================================== */
/* 2. Kamera görüş konisi                                              */
/* ================================================================== */

export const CameraCone: React.FC<{apex: [number, number]; spread?: number; depth?: number; delay?: number}> = ({
  apex,
  spread = 430,
  depth = 470,
  delay = 0,
}) => {
  const frame = useCurrentFrame();
  const p = inAt(frame, delay, 24);
  const [ax, ay] = apex;
  const by = ay + depth;
  return (
    <svg viewBox="0 0 1080 1920" style={{position: "absolute", inset: 0, width: "100%", height: "100%", zIndex: 30}}>
      <defs>
        <linearGradient id="coneFade" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={C.accent} stopOpacity="0.22" />
          <stop offset="1" stopColor={C.accent} stopOpacity="0" />
        </linearGradient>
      </defs>
      <g opacity={p}>
        <path d={`M ${ax} ${ay} L ${ax - spread} ${by} L ${ax + spread} ${by} Z`} fill="url(#coneFade)" />
        <path d={`M ${ax} ${ay} L ${ax - spread * p} ${ay + depth * p}`} stroke={C.accent} strokeWidth="1.5" strokeDasharray="9 10" />
        <path d={`M ${ax} ${ay} L ${ax + spread * p} ${ay + depth * p}`} stroke={C.accent} strokeWidth="1.5" strokeDasharray="9 10" />
        {[0.42, 0.72, 1].map((k) => (
          <path
            key={k}
            d={`M ${ax - spread * k} ${ay + depth * k} L ${ax + spread * k} ${ay + depth * k}`}
            stroke={C.accent}
            strokeOpacity={0.28 * interpolate(p, [k * 0.7, Math.min(1, k * 0.7 + 0.3)], [0, 1], clamp)}
            strokeWidth="1.5"
          />
        ))}
      </g>
    </svg>
  );
};

/* ================================================================== */
/* 3. Güzergâh haritası                                                */
/* ================================================================== */

/** Düzensiz aralıklı sokak ağı — kusursuz ızgara "şablon" gibi durur. */
const H_ROADS = [30, 78, 132, 196, 244, 286];
const V_ROADS = [58, 132, 208, 296, 370, 452, 540, 618, 704, 796, 866];

/** Su kenarı ve park: haritayı gerçek bir yer gibi gösteren iki referans. */
const WATER = "M 0 286 C 130 276, 250 296, 392 288 C 540 280, 660 300, 904 292 L 904 320 L 0 320 Z";
const PARK = {x: 452, y: 196, w: 88, h: 48};

/** Güzergâh: sokakları takip eden, kadraj içinde kalan kapalı bir hat. */
const PTS: [number, number][] = [
  [58, 244], [208, 244], [208, 196], [370, 196], [370, 132],
  [540, 132], [540, 78], [704, 78], [704, 196], [866, 196],
];
const ROUTE = PTS.map(([x, y], i) => `${i === 0 ? "M" : "L"} ${x} ${y}`).join(" ");

export const RouteMap: React.FC<{w?: number; h?: number; delay?: number}> = ({w = 904, h = 300, delay = 0}) => {
  const frame = useCurrentFrame();
  const draw = interpolate(frame, [delay, delay + 74], [0, 1], {...clamp, easing: Easing_inOut});
  const pins: [number, number, number][] = [
    [208, 220, 0.2],
    [452, 132, 0.48],
    [704, 132, 0.76],
  ];
  return (
    <svg viewBox="0 0 904 300" width={w} height={h} style={{display: "block"}}>
      <defs>
        <clipPath id="mapClip">
          <rect x="0" y="0" width="904" height="300" />
        </clipPath>
      </defs>
      <g clipPath="url(#mapClip)">
        <rect x="0" y="0" width="904" height="300" fill="#060B14" />

        {/* yapı adaları */}
        {V_ROADS.slice(0, -1).map((x, i) =>
          H_ROADS.slice(0, -1).map((y, j) => (
            <rect
              key={`b${i}-${j}`}
              x={x + 5}
              y={y + 5}
              width={V_ROADS[i + 1] - x - 10}
              height={H_ROADS[j + 1] - y - 10}
              fill={`rgba(150,182,220,${0.03 + ((i * 7 + j * 3) % 5) * 0.011})`}
            />
          )),
        )}

        {/* park ve su — yön duygusu veren iki referans */}
        <rect x={PARK.x} y={PARK.y} width={PARK.w} height={PARK.h} fill="rgba(47,207,155,.10)" stroke="rgba(47,207,155,.24)" strokeWidth="1" />
        <path d={WATER} fill="rgba(39,182,230,.09)" />
        <path d="M 0 286 C 130 276, 250 296, 392 288 C 540 280, 660 300, 904 292" fill="none" stroke="rgba(39,182,230,.28)" strokeWidth="1.5" />

        {/* sokak ağı */}
        <g stroke="rgba(150,182,220,.16)" strokeWidth="1.2">
          {H_ROADS.map((y) => (
            <line key={`h${y}`} x1="0" y1={y} x2="904" y2={y} />
          ))}
          {V_ROADS.map((x) => (
            <line key={`v${x}`} x1={x} y1="0" x2={x} y2="286" />
          ))}
        </g>
        {/* ana arterler biraz daha kalın */}
        <g stroke="rgba(150,182,220,.30)" strokeWidth="3">
          <line x1="0" y1="244" x2="904" y2="244" />
          <line x1="370" y1="0" x2="370" y2="286" />
        </g>

        {/* güzergâh */}
        <path d={ROUTE} fill="none" stroke="rgba(39,182,230,.14)" strokeWidth="13" strokeLinejoin="round" strokeLinecap="round" />
        <path
          d={ROUTE}
          fill="none"
          stroke={C.accent}
          strokeWidth="3.5"
          strokeLinejoin="round"
          strokeLinecap="round"
          pathLength="1"
          strokeDasharray="1"
          strokeDashoffset={1 - draw}
        />

        {/* başlangıç ve bitiş */}
        <circle cx={PTS[0][0]} cy={PTS[0][1]} r="6" fill="#060B14" stroke={C.accent} strokeWidth="2.5" opacity={draw > 0 ? 1 : 0} />
        <g opacity={interpolate(draw, [0.94, 1], [0, 1], clamp)}>
          <rect x={PTS[9][0] - 7} y={PTS[9][1] - 7} width="14" height="14" fill="#060B14" stroke={C.accent} strokeWidth="2.5" />
        </g>

        {/* tespit iğneleri — drone rota üzerinde ilerledikçe düşer */}
        {pins.map(([x, y, at], i) => {
          const p = interpolate(draw, [at, at + 0.08], [0, 1], clamp);
          return (
            <g key={i} opacity={p}>
              <circle cx={x} cy={y} r={8 + (1 - p) * 14} fill="none" stroke={C.warn} strokeWidth="1.5" opacity={0.55} />
              <path d={`M ${x} ${y - 13} L ${x + 7} ${y - 3} L ${x} ${y + 7} L ${x - 7} ${y - 3} Z`} fill={C.warn} />
            </g>
          );
        })}

        <RouteDrone progress={draw} />

        {/* ölçek ve yön — güzergâhın uzağında, sağ alt köşede */}
        <g opacity="0.8">
          <path d="M 756 272 h 62" stroke={C.dim} strokeWidth="1.5" />
          <path d="M 756 268 v 8 M 818 268 v 8" stroke={C.dim} strokeWidth="1.5" />
          <text x="826" y="277" fill={C.faint} fontFamily={FONT.mono} fontSize="13" letterSpacing="1">
            500 m
          </text>
          <path d="M 34 40 L 40 22 L 46 40 L 40 34 Z" fill={C.dim} />
          <text x="40" y="55" textAnchor="middle" fill={C.faint} fontFamily={FONT.mono} fontSize="12">
            N
          </text>
        </g>
      </g>
      <rect x="0.5" y="0.5" width="903" height="299" fill="none" stroke={C.line} strokeWidth="1" />
    </svg>
  );
};

/** Uçuş koridoru üzerinde ilerleyen drone işareti. */
const RouteDrone: React.FC<{progress: number}> = ({progress}) => {
  const pts = PTS;
  const segs = pts.slice(1).map((p, i) => Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]));
  const total = segs.reduce((a, b) => a + b, 0);
  let d = progress * total;
  let x = pts[0][0];
  let y = pts[0][1];
  for (let i = 0; i < segs.length; i++) {
    if (d <= segs[i]) {
      const k = segs[i] === 0 ? 0 : d / segs[i];
      x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * k;
      y = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * k;
      break;
    }
    d -= segs[i];
    x = pts[i + 1][0];
    y = pts[i + 1][1];
  }
  return (
    <g opacity={progress > 0.01 && progress < 0.999 ? 1 : 0}>
      <circle cx={x} cy={y} r="17" fill={C.accent} fillOpacity="0.14" />
      <circle cx={x} cy={y} r="7" fill={C.accent} stroke="#060B14" strokeWidth="2.5" />
    </g>
  );
};

const Easing_inOut = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

/* ================================================================== */
/* 4. Kapsama grafiği                                                  */
/* ================================================================== */

const SERIES = [8, 14, 19, 27, 33, 38, 46, 51, 57, 61, 66, 70, 73, 77, 80, 82, 85, 87, 89, 91];

const VW = 904;
const VH = 600;

export const CoverageChart: React.FC<{w?: number; h?: number; delay?: number}> = ({w = VW, h = VH, delay = 0}) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [delay, delay + 78], [0, 1], {...clamp, easing: ease});
  const PL = 78; // sol eksen payı
  const PR = 46; // son noktanın etiketi için pay
  const PT = 52; // üst başlık şeridi
  const PB = 54;
  const iw = VW - PL - PR;
  const ih = VH - PT - PB;
  const X = (i: number) => PL + (i / (SERIES.length - 1)) * iw;
  const Y = (v: number) => PT + ih - (v / 100) * ih;
  const line = SERIES.map((v, i) => `${i === 0 ? "M" : "L"} ${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join(" ");
  const area = `${line} L ${X(SERIES.length - 1)} ${Y(0)} L ${X(0)} ${Y(0)} Z`;
  const targetY = Y(90);
  const headI = Math.min(SERIES.length - 1, Math.floor(p * (SERIES.length - 1)));

  return (
    <svg viewBox={`0 0 ${VW} ${VH}`} width={w} height={h} style={{display: "block"}}>
      <defs>
        <linearGradient id="covArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={C.accent} stopOpacity="0.30" />
          <stop offset="1" stopColor={C.accent} stopOpacity="0.01" />
        </linearGradient>
        <clipPath id="covReveal">
          <rect x="0" y="0" width={PL + iw * p + 2} height={VH} />
        </clipPath>
      </defs>

      {/* grafik başlığı — eksen etiketleriyle çakışmasın diye üstte */}
      <text x="0" y="16" fill={C.dim} fontFamily={FONT.mono} fontSize="16" letterSpacing="1.6">
        HAFTALIK YOL AĞI KAPSAMASI
      </text>
      <text x={VW} y="16" textAnchor="end" fill={C.faint} fontFamily={FONT.mono} fontSize="15" letterSpacing="1.2">
        1 KORİDOR · 1 DRONE · 30 GÜN
      </text>
      <line x1="0" y1="30" x2={VW} y2="30" stroke={C.line} strokeWidth="1" />

      {/* ızgara + y ekseni */}
      {[0, 25, 50, 75, 100].map((v) => (
        <g key={v}>
          <line x1={PL} y1={Y(v)} x2={PL + iw} y2={Y(v)} stroke={C.line} strokeWidth="1" strokeDasharray={v === 0 ? undefined : "3 6"} />
          <text x={PL - 16} y={Y(v) + 6} textAnchor="end" fill={C.faint} fontFamily={FONT.mono} fontSize="17">
            %{v}
          </text>
        </g>
      ))}

      {/* hedef çizgisi — etiket solda, son nokta etiketiyle çakışmaz */}
      <g opacity={inAt(frame, delay + 46, 20)}>
        <line x1={PL} y1={targetY} x2={PL + iw} y2={targetY} stroke={C.ok} strokeWidth="1.5" strokeDasharray="8 7" />
        <rect x={PL + 10} y={targetY - 32} width="206" height="26" fill="rgba(5,7,14,.92)" stroke={C.ok} strokeWidth="1" />
        <text x={PL + 22} y={targetY - 13} fill={C.ok} fontFamily={FONT.mono} fontSize="16" letterSpacing="1.4">
          PİLOT HEDEFİ · %90
        </text>
      </g>

      {/* seri */}
      <g clipPath="url(#covReveal)">
        <path d={area} fill="url(#covArea)" />
        <path d={line} fill="none" stroke={C.accent} strokeWidth="3.5" strokeLinejoin="round" strokeLinecap="round" />
      </g>

      {/* okunan son nokta */}
      <g opacity={p > 0.05 ? 1 : 0}>
        <circle cx={X(headI)} cy={Y(SERIES[headI])} r="7" fill={C.ink} stroke={C.accent} strokeWidth="3.5" />
        <text
          x={headI > 14 ? X(headI) : X(headI) + 16}
          y={Y(SERIES[headI]) - 20}
          textAnchor={headI > 14 ? "end" : "start"}
          fill={C.text}
          fontFamily={FONT.mono}
          fontSize="24"
          fontWeight="600"
        >
          %{SERIES[headI]}
        </text>
      </g>

      {/* x ekseni */}
      <line x1={PL} y1={PT + ih} x2={PL + iw} y2={PT + ih} stroke={C.lineStrong} strokeWidth="1.5" />
      {[0, 6, 12, 19].map((i) => (
        <g key={i}>
          <line x1={X(i)} y1={PT + ih} x2={X(i)} y2={PT + ih + 7} stroke={C.lineStrong} strokeWidth="1.5" />
          <text
            x={X(i)}
            y={PT + ih + 32}
            textAnchor={i === 0 ? "start" : i === 19 ? "end" : "middle"}
            fill={C.faint}
            fontFamily={FONT.mono}
            fontSize="17"
          >
            {i === 0 ? "1. GÜN" : `${Math.round((i / 19) * 30)}. GÜN`}
          </text>
        </g>
      ))}
    </svg>
  );
};
