/**
 * 用途：joinMediaPath 路径编解码回归（防 marked 双重 percent-encode）
 * 运行：node tests/test_join_media_path.mjs
 */
function safeDecodeURIComponent(value) {
  const s = String(value || "");
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
}

function joinMediaPath(articleDir, rel) {
  const raw = safeDecodeURIComponent(String(rel || "").replace(/\\/g, "/").trim());
  const baseParts = String(articleDir || "")
    .replace(/\\/g, "/")
    .split("/")
    .filter((p) => p && p !== ".");
  const relParts = raw.replace(/^\.\/+/, "").split("/");
  const stack = baseParts.slice();
  for (const part of relParts) {
    if (!part || part === ".") continue;
    if (part === "..") {
      if (stack.length) stack.pop();
      continue;
    }
    stack.push(safeDecodeURIComponent(part));
  }
  return "/media/" + stack.map(encodeURIComponent).join("/");
}

const cat = "微信公众号文章";
const folder = "晚上躺着动动脚趾，疏通6条经络，每次5分钟，身体越来越好！";
const plain = `附件资源/${folder}/img_1.gif`;
const preEncoded = plain.split("/").map(encodeURIComponent).join("/");

const fromPlain = joinMediaPath(cat, plain);
const fromEncoded = joinMediaPath(cat, preEncoded);
const expected =
  "/media/" +
  [cat, "附件资源", folder, "img_1.gif"].map(encodeURIComponent).join("/");

function assert(cond, msg) {
  if (!cond) {
    console.error("FAIL:", msg);
    process.exitCode = 1;
  } else {
    console.log("PASS:", msg);
  }
}

assert(fromPlain === expected, "plain Chinese relative path");
assert(fromEncoded === expected, "marked-style percent-encoded relative path");
assert(!fromEncoded.includes("%25"), "no double-encoding (%25)");
assert(joinMediaPath(cat, "../x.png") === "/media/x.png", "parent segment ..");
assert(joinMediaPath("", "a/b.png") === "/media/a/b.png", "root category");

if (process.exitCode) {
  console.error({ fromPlain, fromEncoded, expected });
} else {
  console.log("all joinMediaPath cases passed");
}
