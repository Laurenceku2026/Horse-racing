const express = require('express');
const cors = require('cors');
const { createClient } = require('@supabase/supabase-js');
const { HorseRacingAPI } = require('@gikndue/hkjc-api');

const app = express();
const PORT = process.env.PORT || 3000;

// 中间件
app.use(cors());
app.use(express.json());

// Supabase 客户端
const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
const supabase = createClient(supabaseUrl, supabaseKey);

// HKJC API 客户端
const horseAPI = new HorseRacingAPI();

// ==================== 健康检查 ====================
app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// ==================== 获取今日赛马日 ====================
app.get('/api/meetings', async (req, res) => {
    try {
        const activeMeetings = await horseAPI.getActiveMeetings();
        // 确保返回格式是 { success: true, data: [...] }
        res.json({ success: true, data: activeMeetings });
    } catch (error) {
        console.error('获取赛马日失败:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// ==================== 同步单场赛事到 Supabase ====================
app.post('/api/sync/race', async (req, res) => {
    const { date, venue, raceNo } = req.body;
    
    console.log(`开始同步: ${date} ${venue} 第${raceNo}场`);
    
    try {
        // 1. 从 HKJC API 获取赛事信息
        const race = await horseAPI.getRaceWithDateAndVenueCode(date, venue, parseInt(raceNo));
        
        if (!race) {
            return res.json({ success: false, error: '未找到赛事数据' });
        }
        
        // 2. 获取赔率
        let oddsData = null;
        try {
            oddsData = await horseAPI.getRaceOddsWithDateAndVenueCode(date, venue, parseInt(raceNo), ['WIN', 'PLA', 'QIN']);
        } catch (oddsErr) {
            console.log('获取赔率失败，继续同步其他数据:', oddsErr.message);
        }
        
        // 3. 保存赛事主表
        const { error: raceError } = await supabase
            .schema('racing')
            .from('races')
            .upsert({
                race_date: date,
                venue: venue,
                race_no: parseInt(raceNo),
                distance: race.distance || 0,
                surface: race.surface || '草地',
                going: race.going || '好地',
                race_class: race.raceClass || '',
                total_runners: race.runners?.length || 0,
                race_status: 'RUNNERS',
                updated_at: new Date().toISOString()
            }, { onConflict: 'race_date,venue,race_no' });
        
        if (raceError) {
            console.error('保存赛事失败:', raceError);
        }
        
        // 4. 保存马匹和出赛信息
        if (race.runners && race.runners.length > 0) {
            for (const runner of race.runners) {
                // 保存马匹
                await supabase
                    .schema('racing')
                    .from('horses')
                    .upsert({
                        name_zh: runner.horseNameZh || '',
                        name_en: runner.horseNameEn || '',
                        age: runner.age,
                        sex: runner.sex
                    }, { onConflict: 'name_en' });
                
                // 保存骑师
                if (runner.jockeyEn) {
                    await supabase
                        .schema('racing')
                        .from('jockeys')
                        .upsert({
                            name_zh: runner.jockeyZh || '',
                            name_en: runner.jockeyEn
                        }, { onConflict: 'name_en' });
                }
                
                // 获取该马的赔率
                let winOdds = null;
                if (oddsData && oddsData.WIN) {
                    const horseOdds = oddsData.WIN.find(o => o.horseNo === runner.horseNo);
                    if (horseOdds) winOdds = horseOdds.odds;
                }
                
                // 保存出赛记录
                await supabase
                    .schema('racing')
                    .from('race_runners')
                    .upsert({
                        race_date: date,
                        race_no: parseInt(raceNo),
                        venue: venue,
                        horse_name: runner.horseNameEn,
                        horse_no: runner.horseNo,
                        draw: runner.draw,
                        actual_weight: runner.actualWeight,
                        rating: runner.rating,
                        jockey_name: runner.jockeyEn,
                        odds_win: winOdds
                    }, { onConflict: 'race_date,race_no,venue,horse_no' });
            }
        }
        
        console.log(`同步完成: ${date} ${venue} 第${raceNo}场, ${race.runners?.length || 0} 匹马`);
        res.json({ 
            success: true, 
            message: `同步成功: ${date} ${venue} 第${raceNo}场`,
            data: { runners: race.runners?.length || 0 }
        });
        
    } catch (error) {
        console.error('同步失败:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// ==================== 批量同步全天赛事 ====================
app.post('/api/sync/day', async (req, res) => {
    const { date } = req.body;
    
    console.log(`开始批量同步: ${date}`);
    
    try {
        // 获取该日期的所有赛事
        const allRaces = await horseAPI.getAllRaces();
        const targetMeeting = allRaces.find(m => m.date === date);
        
        if (!targetMeeting || !targetMeeting.races) {
            return res.json({ success: false, error: `未找到 ${date} 的赛事` });
        }
        
        const results = [];
        for (const race of targetMeeting.races) {
            try {
                // 调用同步接口
                const syncResult = await fetch(`${req.protocol}://${req.get('host')}/api/sync/race`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ date, venue: targetMeeting.venueCode, raceNo: race.raceNo })
                });
                const data = await syncResult.json();
                results.push({ raceNo: race.raceNo, success: data.success });
            } catch (err) {
                results.push({ raceNo: race.raceNo, success: false, error: err.message });
            }
        }
        
        res.json({ success: true, message: `同步完成: ${date}`, results });
        
    } catch (error) {
        console.error('批量同步失败:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// 启动服务器
app.listen(PORT, '0.0.0.0', () => {
    console.log(`HKJC API Server running on port ${PORT}`);
});
