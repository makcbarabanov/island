#!/usr/bin/env node
/**
 * Парсит chat.txt и генерирует stat.html с встроенными сообщениями.
 * Запуск: node build-stat.mjs
 */
import { readFileSync, writeFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const ROOT = dirname(fileURLToPath(import.meta.url));
const chatText = readFileSync(join(ROOT, 'chat.txt'), 'utf8');
const aliases = JSON.parse(readFileSync(join(ROOT, 'name-aliases.json'), 'utf8'));

const HEADER_RE = /^\[(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})\]\s+(.+?):\s*$/;

function normalizeAuthor(raw) {
  if (raw.startsWith('***')) return 'Система';
  return aliases.aliases[raw] ?? raw;
}

function parseChat(text) {
  const lines = text.split('\n');
  const messages = [];
  let i = 0;
  let id = 0;

  while (i < lines.length) {
    const line = lines[i];
    const m = line.match(HEADER_RE);
    if (!m) {
      i++;
      continue;
    }
    const [, dd, mm, yyyy, hh, min, authorRaw] = m;
    const bodyLines = [];
    i++;
    while (i < lines.length && !lines[i].match(HEADER_RE)) {
      if (lines[i] !== '' || bodyLines.length > 0) bodyLines.push(lines[i]);
      i++;
    }
    while (bodyLines.length > 0 && bodyLines[bodyLines.length - 1] === '') {
      bodyLines.pop();
    }
    const textBody = bodyLines.join('\n');
    id++;
    messages.push({
      id,
      datetime: `${dd}.${mm}.${yyyy} ${hh}:${min}`,
      date: `${dd}.${mm}.${yyyy}`,
      year: +yyyy,
      month: +mm,
      day: +dd,
      authorRaw,
      author: normalizeAuthor(authorRaw),
      text: textBody,
      isSystem: authorRaw.startsWith('***'),
    });
  }
  return messages;
}

function isRelevantWindow(msg) {
  const { year, month, day } = msg;
  if (year !== 2026) return false;
  if (month === 5 && day >= 25) return true;
  if (month === 6 && day <= 22) return true;
  return false;
}

function isMediaOnly(text) {
  const t = text.trim();
  return /^\[(видеосообщение|файл|фото|стикер|голосовое сообщение)([^\]]*)\]$/i.test(t);
}

function hasNumberedHabits(text) {
  const lines = text.split('\n').slice(0, 20);
  let numbered = 0;
  for (const line of lines) {
    if (/^\s*\d+[\.\)]\s+\S/.test(line)) numbered++;
  }
  return numbered >= 2;
}

function classify(msg) {
  if (msg.isSystem || isMediaOnly(msg.text)) return 'simple';

  const text = msg.text;
  const lower = text.toLowerCase();
  const firstLines = text.split('\n').slice(0, 5).join('\n').toLowerCase();
  const intro = lower.slice(0, 400);

  if (/\bманифест\b/.test(intro) && !/отч[её]т\s*(за\s+)?\d/i.test(firstLines)) {
    return 'manifest';
  }
  if (/мои\s+цели\s+на\s+марафон/.test(intro) && !/\bотч[её]т\b/i.test(firstLines)) {
    return 'manifest';
  }

  const reportMarkers = [
    /\bотч[её]т\b/,
    /\bмой\s+отч[её]т\b/,
    /отч[её]т\s+за\s/,
    /отч[её]т\s+\d/,
    /мои\s+успехи\s+за\s+\d/,
    /^отч[её]т\s+\d/i,
  ];
  const hasReportMarker = reportMarkers.some((re) => re.test(firstLines) || re.test(lower.slice(0, 200)));
  const hasCheckmarks = /[✅❌🟡]/.test(text);
  const hasDoneWords = /\b(сделал[аи]?|не\s+сделал[аи]?|не\s+выполнен[оа]?|выполнен[оа]?\s+с\s+опозданием)\b/i.test(text);
  const hasReportDate = /отч[её]т\s*(за\s*)?\d{1,2}[\.\/_]\s*\d{1,2}/i.test(firstLines);

  if (hasReportMarker || (hasCheckmarks && hasNumberedHabits(text)) || (hasReportDate && hasNumberedHabits(text))) {
    if (!/^(мои\s+(цели|привычки|планы))/i.test(firstLines.trim()) || /\bотч[её]т\b/i.test(firstLines)) {
      return 'report';
    }
  }
  if (hasCheckmarks && /\(\d+\/\d+\)/.test(text)) return 'report';
  if (hasDoneWords && hasNumberedHabits(text) && /\d{1,2}[\.\/_]\d{1,2}/.test(firstLines)) return 'report';

  const manifestMarkers = [
    /\bманифест\b/,
    /мои\s+привычки/,
    /мои\s+планы\s+на/,
    /мои\s+цели\s+на\s+(марафон|июн|91)/,
    /мои\s+цели\s*-/,
    /формирую\s+следующие\s+привычки/,
    /привычки,?\s+которые\s+я\s+беру/,
    /мои\s+цели\s+на\s+91\s+день/,
  ];
  const isManifestKeyword = manifestMarkers.some((re) => re.test(lower));
  const isEarlyCycle =
    (msg.month === 5 && msg.day >= 28) ||
    (msg.month === 6 && msg.day <= 3);

  if (isManifestKeyword) {
    const looksLikeReport = /\bотч[её]т\b/i.test(firstLines) && !/^↩/.test(text);
    if (!looksLikeReport) return 'manifest';
  }
  if (hasNumberedHabits(text) && isEarlyCycle && !hasCheckmarks && !/\bотч[её]т\b/i.test(lower.slice(0, 100))) {
    if (/мои\s+цел/i.test(lower) || /привычк/i.test(lower) || /марафон/i.test(lower)) {
      return 'manifest';
    }
  }

  if (/^благодарю[:\s]/im.test(text) && !hasCheckmarks && !hasNumberedHabits(text)) {
    return 'simple';
  }

  return 'simple';
}

const messages = parseChat(chatText).map((msg) => ({
  ...msg,
  opinion: classify(msg),
  inWindow: isRelevantWindow(msg),
}));

const template = readFileSync(join(ROOT, 'stat.template.html'), 'utf8');
const html = template.replace('/*__MESSAGES__*/', JSON.stringify(messages));
writeFileSync(join(ROOT, 'stat.html'), html, 'utf8');

const counts = { simple: 0, manifest: 0, report: 0 };
for (const m of messages) counts[m.opinion]++;
console.log(`stat.html: ${messages.length} сообщений`);
console.log(`Мнение: простое=${counts.simple}, манифест=${counts.manifest}, отчёт=${counts.report}`);
console.log(`В окне мая–22.06: ${messages.filter((m) => m.inWindow).length}`);
