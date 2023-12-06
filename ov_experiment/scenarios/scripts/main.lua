function initialize(box)
    dofile(box:get_config("${Path_Data}") .. "/plugins/stimulation/lua-stimulator-stim-codes.lua")
    dofile(box:get_config("${Player_ScenarioDirectory}") .. "/scripts/stimuli.lua")

    -- TODO: don't hardcode these
    local numTrials_A_X = 144
    local numTrials_nA_nX = 48
    durations = {
        ISI=0.250, --s
        ITI={1.500, 2.000, 2.500}, --s, these are the set of possible ITIs
        cueStim=0.250, --s
        probeStim=0.250 --s
    }

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

    -- Create the list of ITI times for each trial
    ITI = {}
    for k=1,#trials do
        table.insert(ITI, durations.ITI[k % #durations.ITI + 1])
    end
    -- shuffle the ITIs
    ITI = shuffle_arr(ITI)
end

-- this function is called once by the box
function process(box)

	local t = box:get_current_time()

    -- Start the experiment
    box:send_stimulation(1, stimcodes.experiment_start, t, 0)

    -- Display the instructions
    for k, stim in ipairs(stimcodes.instructions) do
        box:send_stimulation(1, stim, t, 0)
        t = wait_for_continue(box)
    end

    -- Iterate through trials
    for k_t, trial in ipairs(trials) do
        -- Assume that at start of loop, `t` is the time of the start of 
        -- the trial

        -- Indicate start of trial
        box:send_stimulation(1, stimcodes.trial_start, t, 0)

        -- Show fixation cross
        box:send_stimulation(1, stimcodes.fixation_cross, t, 0)
        t = t + durations.ISI

        -- Show the cue stimulus
        box:send_stimulation(1, trial.cue, t, 0)
        t = t + durations.cueStim

        -- Show fixation cross
        box:send_stimulation(1, stimcodes.fixation_cross, t, 0)
        t = t + durations.ISI

        -- Show the probe stimulus
        box:send_stimulation(1, trial.probe, t, 0)
        t = t + durations.probeStim

        -- End the trial and wait for the next trial
        box:send_stimulation(1, stimcodes.trial_stop, t, 0)
        box:send_stimulation(1, stimcodes.clear_screen, t, 0)
        t = t + ITI[k_t]
    end

    -- end the experiment
    box:send_stimulation(1, stimcodes.experiment_stop, t, 0)
end

function wait_for_continue(box)
    -- loop until box:keep_processing() returns zero
	-- cpu will be released with a call to sleep
	-- at the end of the loop
    while box:keep_processing() do

        -- specify the stimulation that implies to stop waiting
        local target_stimulation = OVTK_StimulationId_Number_1B

        -- get current simulated time
        local t = box:get_current_time()

        -- loop through all inputs of the box
        for input = 1, box:get_input_count() do
            
            -- loop through every received stimulation for the input
            for stimulation = 1, box:get_stimulation_count(input) do

                -- get the received stimulation and discard it
                local identifier, _, _ = box:get_stimulation(input, 1)
                box:remove_stimulation(input, 1)

                -- return the time if the target stimulation is was received
                if identifier == target_stimulation then
                    return t
                end

            end

        end
        
        -- release cpu
        box:sleep()
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

function wait_until(box, time)  
    while box:get_current_time() < time do  
      box:sleep()  
    end  
end 
