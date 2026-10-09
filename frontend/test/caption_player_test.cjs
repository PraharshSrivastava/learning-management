const {test} = require('node:test');
const assert = require('node:assert/strict');
const {captionUrls,parseVtt,activeCue,sha256} = require('../web/caption-player.js');
test('caption integrity works on HTTP and Unicode',()=>{
 const {createHash}=require('node:crypto');
 for(const value of ['', 'abc', '₹100 & completed.', 'a'.repeat(10000)])assert.equal(sha256(value),createHash('sha256').update(value).digest('hex'));
});
test('asset URLs retain deployment prefix and query string',()=>{
 const urls=captionUrls('https://example.com/lms/assets/videos/m.MP4?token=abc');
 assert.equal(urls.vtt.href,'https://example.com/lms/assets/videos/m.vtt?token=abc');
 assert.equal(captionUrls('https://example.com/video.webm'),null);
});
test('cue boundaries and silent gaps follow actual media time',()=>{
 const cues=parseVtt('WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nSave &amp; upload.\n\n00:00:02.000 --> 00:00:03.000\nNext.\n');
 assert.equal(activeCue(cues,0),'Save & upload.');assert.equal(activeCue(cues,1),'');assert.equal(activeCue(cues,2),'Next.');assert.equal(activeCue(cues,3),'');
});
test('malformed or overlapping tracks fail closed',()=>{
 for(const vtt of ['garbage','WEBVTT\n\n00:00:00.000 --> 00:00:00.000\nNo','WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nFirst\n\n00:00:01.000 --> 00:00:03.000\nSecond'])assert.throws(()=>parseVtt(vtt));
});
