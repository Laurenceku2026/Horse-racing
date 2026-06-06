const express = require('express');
const cors = require('cors');
const { createClient } = require('@supabase/supabase-js');
const { HorseRacingAPI } = require('@gikndue/hkjc-api');

const app = express();
const PORT = process.env.PORT || 3000;

// 中间件
app.use(cors());
app.use(express.json());

// Supabase 客户端（默认使用 public schema）
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

// ==================== 同步单场赛事 ====================
app.post('/api/sync/race', async (req, res) => {
    const { date, venue, raceNo } = req.body;
    
    console.log(`[开始同步] ${date} ${venue} 第${raceNo}场`);
    
    try {
        // 1. 获取赛事详情
        const raceDetails = await horseAPI.getRaceWithDateAndVenueCode(date, venue, parseInt(raceNo));
        
        if (!raceDetails) {
            return res.json({ success: false, error: '未找到赛事数据' });
        }
        
        console.log(`[API返回] 距离=${raceDetails.distance}, 马匹数=${raceDetails.runners?.length}`);
        
        // 2. 获取赔率
        let oddsData = null;
        try {
            oddsData = await horseAPI.getRaceOddsWithDateAndVenueCode(date, venue, parseInt(raceNo), ['WIN']);
        } catch (oddsErr) {
            console.log('获取赔率失败:', oddsErr.message);
        }
        
        // ========== 3. 保存到 races 表 ==========
        const { error: raceError } = await supabase
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
            }, { onConflict: 'race_date,venue,race_no' });
        
        if (raceError) {
            console.error('保存赛事失败:', raceError);
        } else {
            console.log('保存赛事成功');
        }
        
        // ========== 4. 遍历 runners ==========
        const runners = raceDetails.runners || [];
        
        for (const runner of runners) {
            // 🔧 调试：打印 runner 的原始结构（只打印第一匹马）
            if (runners.indexOf(runner) === 0) {
                console.log('runner 数据结构示例:', JSON.stringify(runner, null, 2));
            }
            
            // 4.1 获取马名（尝试多个可能的字段名）
            const horseName = runner.horseName || runner.name || runner.horse_name || 'Unknown';
            
            // 4.2 获取骑师名（可能是一个对象，需要提取 name_en）
            let jockeyName = null;
            let jockeyNameZh = null;
            if (runner.jockey) {
                if (typeof runner.jockey === 'object') {
                    jockeyName = runner.jockey.name_en || runner.jockey.name || runner.jockey.name_ch;
                    jockeyNameZh = runner.jockey.name_ch || null;
                } else {
                    jockeyName = runner.jockey;
                }
            }
            
            // 4.3 保存马匹
            if (horseName && horseName !== 'Unknown') {
                const { error: horseError } = await supabase
                    .from('horses')
                    .upsert({
                        name_en: horseName,
                        name_zh: runner.horseNameZh || null,
                        age: runner.age || null,
                        sex: runner.sex || null
                    }, { onConflict: 'name_en' });
                
                if (horseError) {
                    console.error(`保存马匹失败 ${horseName}:`, horseError);
                }
            }
            
            // 4.4 保存骑师
            if (jockeyName) {
                const { error: jockeyError } = await supabase
                    .from('jockeys')
                    .upsert({
                        name_en: jockeyName,
                        name_zh: jockeyNameZh || null
                    }, { onConflict: 'name_en' });
                
                if (jockeyError) {
                    console.error(`保存骑师失败 ${jockeyName}:`, jockeyError);
                }
            }
            
            // 4.5 获取赔率
            let winOdds = null;
            if (oddsData && oddsData.WIN) {
                const horseOdds = oddsData.WIN.find(o => o.horseNo === runner.horseNo);
                if (horseOdds) winOdds = horseOdds.odds;
            }
            
            // 4.6 保存出赛记录
            const { error: runnerError } = await supabase
                .from('race_runners')
                .upsert({
                    race_date: date,
                    race_no: parseInt(raceNo),
                    venue: venue,
                    horse_name: horseName,
                    horse_no: runner.horseNo || runner.number,
                    draw: runner.draw,
                    actual_weight: runner.actualWeight,
                    rating: runner.rating,
                    jockey_name: jockeyName,
                    odds_win: winOdds
                }, { onConflict: 'race_date,venue,race_no,horse_no' });
            
            if (runnerError) {
                console.error('保存出赛记录失败:', runnerError);
            } else {
                console.log(`保存出赛记录成功: ${horseName}`);
            }
        }
        
        console.log(`[同步完成] ${date} ${venue} 第${raceNo}场, ${runners.length} 匹马`);
        res.json({ 
            success: true, 
            message: `同步成功: ${date} ${venue} 第${raceNo}场`,
            data: { runners: runners.length }
        });
        
    } catch (error) {
        console.error('同步失败:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`HKJC API Server running on port ${PORT}`);
});
