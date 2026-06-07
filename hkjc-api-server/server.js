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
        // 1. 从 HKJC API 获取赛事信息
        const raceDetails = await horseAPI.getRaceWithDateAndVenueCode(date, venue, parseInt(raceNo));
        
        if (!raceDetails) {
            return res.json({ success: false, error: '未找到赛事数据' });
        }
        
        console.log(`[API返回] 距离=${raceDetails.distance}, 马匹数=${raceDetails.runners?.length}`);
        
        // 2. 获取赔率
        let oddsData = null;
        try {
            oddsData = await horseAPI.getRaceOddsWithDateAndVenueCode(date, venue, parseInt(raceNo), ['WIN', 'PLA', 'QIN']);
            if (oddsData && oddsData.WIN) {
                console.log(`[赔率] 获取成功，WIN赔率数量: ${oddsData.WIN.length}`);
            } else {
                console.log(`[赔率] 无数据`);
            }
        } catch (oddsErr) {
            console.error(`[赔率] 获取失败: ${oddsErr.message}`);
        }
        
        // ========== 3. 保存 races 主表 ==========
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
            // 获取马匹信息
            const horseId = runner.id || runner.horseId || '';
            const horseName = runner.name_en || runner.horseName || 'Unknown';
            const horseNo = parseInt(runner.no) || 0;
            const draw = parseInt(runner.barrierDrawNumber) || 0;
            const actualWeight = parseInt(runner.handicapWeight) || 0;
            const rating = parseInt(runner.internationalRating) || 0;
            
            // 骑师信息
            let jockeyName = '';
            if (runner.jockey) {
                jockeyName = runner.jockey.name_en || '';
            }
            
            // 中文名
            const horseNameZh = runner.name_ch || '';
            
            // 获取赔率
            let winOdds = null;
            if (oddsData && oddsData.WIN) {
                const horseOdds = oddsData.WIN.find(o => o.horseNo === horseNo);
                if (horseOdds) {
                    winOdds = horseOdds.odds;
                }
            }
            
            // 保存马匹到 horses 表
            if (horseId) {
                await supabase
                    .from('horses')
                    .upsert({
                        hkjc_id: horseId,
                        name_en: horseName,
                        name_zh: horseNameZh
                    }, { onConflict: 'hkjc_id' });
            }
            
            // 保存骑师
            if (jockeyName) {
                await supabase
                    .from('jockeys')
                    .upsert({
                        name_en: jockeyName,
                        name_zh: runner.jockey?.name_ch || ''
                    }, { onConflict: 'name_en' });
            }
            
            // 保存出赛记录（包含 horse_id）
            const { error: runnerError } = await supabase
                .from('race_runners_clean')
                .upsert({
                    race_date: date,
                    race_no: parseInt(raceNo),
                    venue: venue,
                    horse_id: horseId,
                    horse_name: horseName,
                    horse_name_zh: horseNameZh,
                    horse_no: horseNo,
                    draw: draw,
                    actual_weight: actualWeight,
                    rating: rating,
                    jockey_name: jockeyName,
                    odds_win: winOdds
                }, { onConflict: 'race_date,venue,race_no,horse_no' });
            
            if (runnerError) {
                console.error(`保存出赛记录失败 ${horseName}:`, runnerError);
            } else {
                console.log(`保存马匹: ${horseName}, horse_id: ${horseId}, 档位: ${draw}, 骑师: ${jockeyName}`);
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

// 启动服务器
app.listen(PORT, '0.0.0.0', () => {
    console.log(`HKJC API Server running on port ${PORT}`);
});
