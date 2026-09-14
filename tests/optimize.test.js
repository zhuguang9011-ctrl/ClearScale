const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const sharp = require('sharp');
const { prepare, finish } = require('../src/optimize');

test('reduces flat-surface noise while preserving a material boundary', async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'clear-test-'));
  try {
    const input = path.join(dir, 'input.png'), output = path.join(dir, 'clean.png');
    const data = Buffer.alloc(64*64*3);
    for (let y=0;y<64;y++) for(let x=0;x<64;x++)
      for(let c=0;c<3;c++) data[(y*64+x)*3+c]=(x<32?90:210)+((x+y)%2?8:-8);
    await sharp(data,{raw:{width:64,height:64,channels:3}}).png().toFile(input);
    await prepare(input,output,{denoise:true,evenness:'light'});
    const clean=await sharp(output).raw().toBuffer();
    let oldError=0,newError=0;
    for(let y=8;y<56;y++) for(let x=8;x<24;x++) {
      oldError+=Math.abs(data[(y*64+x)*3]-90);
      newError+=Math.abs(clean[(y*64+x)*3]-90);
    }
    assert.ok(newError < oldError * 0.65);
    assert.ok(clean[(32*64+32)*3]-clean[(32*64+31)*3]>100);
  } finally { await fs.rm(dir,{recursive:true,force:true}); }
});

test('validates native 4x then exports exact 2x/3x sizes and alpha', async () => {
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'clear-size-'));
  try {
    const input=path.join(dir,'in.png'), prepared=path.join(dir,'pre.png'), ai=path.join(dir,'ai.png');
    await sharp({create:{width:16,height:12,channels:4,background:{r:90,g:130,b:180,alpha:0.5}}}).png().toFile(input);
    await prepare(input,prepared,{denoise:false,evenness:'off'});
    await sharp(prepared).resize(64,48).png().toFile(ai);
    for(const scale of [2,3,4]) {
      const out=path.join(dir,scale+'.png');
      await finish(input,prepared,ai,out,{scale,format:'png'});
      const m=await sharp(out).metadata();
      assert.equal(m.width,16*scale); assert.equal(m.height,12*scale); assert.equal(m.hasAlpha,true);
      const a=await sharp(out).extractChannel('alpha').raw().toBuffer();
      assert.ok(Math.abs(a[0]-128)<=1);
    }
    await assert.rejects(finish(input,prepared,prepared,path.join(dir,'bad.png'),{scale:2,format:'png'}),/尺寸异常/);
  } finally { await fs.rm(dir,{recursive:true,force:true}); }
});
