
local function main()
    dofile("ov_experiment/scenarios/scripts/lua-stimulator-stim-codes.lua")

    dofile("ov_experiment/scenarios/scripts/stimuli.lua")

    -- TODO: don't hardcode these
    local numTrials_A_X = 144
    local numTrials_nA_nX = 48

    -- Create the list of trials
    trials = {}
    -- Add the AX trials
    trialAX = {
        cue=stimcodes.alphabet.A,
        probe=stimcodes.alphabet.X
    }
    for _ = 1,numTrials_A_X do
        table.insert(trials, trialAX)
    end
    -- Add the not-A not-X trials
    alphabetCodes = {}
    for _, v in pairs(stimcodes.alphabet) do
        table.insert(alphabetCodes, v)
    end
    for _ = 1,numTrials_nA_nX do
        trial = {}
        repeat
            trial.cue = alphabetCodes[math.random(#alphabetCodes)]
            trial.probe = alphabetCodes[math.random(#alphabetCodes)]
        until trial.cue~=trialAX.cue or trial.probe~=trialAX.probe
        table.insert(trials, trial)
    end
    -- shuffle the trials
    trials = shuffle_arr(trials)

    for k,v in pairs(trials) do
        print(k,v.cue, v.probe)
    end
end





function shuffle_arr(arr)
    local s = {}

    -- copy original array
    for k, _ in ipairs(arr) do
        s[k] = arr[k]
    end

    -- shuffle the copied array
    for i = #arr, 2, -1 do
        local j = math.random(i)
        s[i], s[j] = s[j], s[i]
    end

    return s
end

main()