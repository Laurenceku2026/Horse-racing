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

// ==================== 获取赛马日列表 ====================
app.get('/api/meetings', async (req, res) => {
    try {
        const activeMeetings = await horseAPI.getActiveMeetings();
        res.json({ success: true, data: activeMeetings });
    } catch (error) {
        console.error('获取赛马日失败:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// ==================== 同步单场赛事到 Supabase ====================
app.post('/api/sync/race', async (req, res) => {
    const { date, venue, raceNo } = req.body;
    
    console.log(`[开始同步] ${date} ${venue} 第${raceNo}场`);
    
    try {
        // 1. 从 HKJC API 获取完整的赛事信息
        const raceDetails = await horseAPI.getRaceWithDateAndVenueCode(date, venue, parseInt(raceNo));
        
        if (!raceDetails) {
            console.error(`[错误] 未找到赛事数据: ${date} ${venue} ${raceNo}`);
            return res.json({ success: false, error: '未找到赛事数据' });
        }
        
        console.log(`[API返回] 赛事详情: distance=${raceDetails.distance}, runners=${raceDetails.runners?.length}`);
        
        // 2. 获取赔率
        let oddsData = null;
        try {
            oddsData = await horseAPI.getRaceOddsWithDateAndVenueCode(date, venue, parseInt(raceNo), ['WIN', 'PLA', 'QIN']);
        } catch (oddsErr) {
            console.log('获取赔率失败，继续同步:', oddsErr.message);
        }
        
        // ========== 3. 保存 races 主表 ==========
        console.log(`[保存赛事] race_date=${date}, venue=${venue}, race_no=${raceNo}`);
        const { error: raceError, data: raceData } = await supabase
            .schema('racing')
            .from('races')
            .upsert({
                race_date: date,
                venue: venue,
                race_no: parseInt(raceNo),
                distance: raceDetails.distance || 0,
                surface: raceDetails.surface || '草地',
                going: raceDetails.going || '好地',
                race_class: raceDetails.raceClass || '',
                total_runners: raceDetails.runners?.length || 0,
                race_status: 'RUNNERS',
                updated_at: new Date().toISOString()
            }, { onConflict: 'race_date,venue,race_no' })
            .select();
        
        if (raceError) {
            console.error(`[保存赛事失败] ${JSON.stringify(raceError)}`);
        } else {
            console.log(`[保存赛事成功] ${JSON.stringify(raceData)}`);
        }
        
        // ========== 4. 遍历 runners ==========
        const runners = raceDetails.runners || [];
        console.log(`[处理 runners] 共 ${runners.length} 匹马`);
        
        for (const runner of runners) {
            // 4.1 保存马匹 (horses 表)
            if (runner.horseName) {
                const { error: horseError } = await supabase
                    .schema('racing')
                    .from('horses')
                    .upsert({
                        name_en: runner.horseName,
                        name_zh: runner.horseNameZh || '',
                        age: runner.age || null,
                        sex: runner.sex || null
                    }, { onConflict: 'name_en' });
                
                if (horseError) {
                    console.error(`[保存马匹失败] ${runner.horseName}: ${JSON.stringify(horseError)}`);
                }
            }
            
            // 4.2 保存骑师 (jockeys 表)
            if (runner.jockey) {
                const { error: jockeyError } = await supabase
                    .schema('racing')
                    .from('jockeys')
                    .upsert({
                        name_en: runner.jockey,
                        name_zh: runner.jockeyZh || ''
                    }, { onConflict: 'name_en' });
                
                if (jockeyError) {
                    console.error(`[保存骑师失败] ${runner.jockey}: ${JSON.stringify(jockeyError)}`);
                }
            }
            
            // 4.3 获取该马的赔率
            let winOdds = null;
            if (oddsData && oddsData.WIN) {
                const horseOdds = oddsData.WIN.find(o => o.horseNo === runner.horseNo);
                if (horseOdds) winOdds = horseOdds.odds;
            }
            
            // 4.4 保存出赛记录 (race_runners 表)
            const { error: runnerError } = await supabase
                .schema('racing')
                .from('race_runners')
                .upsert({
                    race_date: date,
                    race_no: parseInt(raceNo),
                    venue: venue,
                    horse_name: runner.horseName,
                    horse_no: runner.horseNo,
                    draw: runner.draw,
                    actual_weight: runner.actualWeight,
                    rating: runner.rating,
                    jockey_name: runner.jockey,
                    odds_win: winOdds
                }, { onConflict: 'race_date,race_no,venue,horse_no' });
            
            if (runnerError) {
                console.error(`[保存出赛记录失败] ${runner.horseName}: ${JSON.stringify(runnerError)}`);
            }
        }
        
        console.log(`[同步完成] ${date} ${venue} 第${raceNo}场, ${runners.length} 匹马`);
        res.json({ 
            success: true, 
            message: `同步成功: ${date} ${venue} 第${raceNo}场`,
            data: { runners: runners.length }
        });
        
    } catch (error) {
        console.error(`[同步异常] ${error.message}`, error.stack);
        res.status(500).json({ success: false, error: error.message });
    }
});

// 启动服务器
app.listen(PORT, '0.0.0.0', () => {
    console.log(`HKJC API Server running on port ${PORT}`);
});
